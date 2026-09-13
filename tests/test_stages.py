from datetime import datetime

import pandas as pd
import pytest

from data_cleaning_agent.contracts import CategoryReport, SchemaReport
from data_cleaning_agent.model import ModelError
from data_cleaning_agent.privacy import PreparedData, prepare_private_data
from data_cleaning_agent.stages.categories import run_categories
from data_cleaning_agent.stages.schema import apply_schema, build_schema_context, run_schema
from data_cleaning_agent.stages.text import run_text


def column(index, original, canonical, kind="string", confidence=0.95):
    return {
        "column_index": index,
        "original_name": original,
        "canonical_name": canonical,
        "column_type": kind,
        "confidence": confidence,
    }


def test_schema_shuffled_indices_and_empty_columns():
    df = pd.DataFrame(
        [["a", "b", " "], ["c", "d", None]], columns=["E-mail", "University Email", "placeholder"]
    )
    before = df.copy(deep=True)
    report = SchemaReport(
        columns=[
            column(2, "placeholder", "invented"),
            column(1, "University Email", "university_email", "email"),
            column(0, "E-mail", "email", "email"),
        ]
    )
    result = apply_schema(df, report)
    assert list(result.dataframe.columns) == ["email", "university_email", "placeholder"]
    pd.testing.assert_frame_equal(df, before)
    assert result.details["columns"][0]["column_type"] == "empty"


@pytest.mark.parametrize(
    "mappings",
    [
        [column(0, "a", "one")],
        [column(0, "a", "one"), column(0, "a", "two")],
        [column(0, "wrong", "one"), column(1, "b", "two")],
        [column(0, "a", None, "empty"), column(1, "b", "two")],
    ],
)
def test_schema_rejects_incomplete_or_conflicting_mappings(mappings):
    df = pd.DataFrame([["x", "y"]], columns=["a", "b"])
    with pytest.raises(ModelError):
        apply_schema(df, SchemaReport(columns=mappings))
    assert list(df.columns) == ["a", "b"]


def test_schema_disambiguates_repeated_semantic_names():
    df = pd.DataFrame([["x", "y"]], columns=["role branch A", "role branch B"])
    report = SchemaReport(
        columns=[column(0, "role branch A", "role"), column(1, "role branch B", "role")]
    )
    result = apply_schema(df, report)
    assert list(result.dataframe.columns) == ["role", "role_2"]
    assert result.issues[-1]["rule"] == "duplicate_canonical_name"


def test_uncertain_schema_preserves_source_name():
    df = pd.DataFrame([["x"]], columns=["Column1"])
    result = apply_schema(df, SchemaReport(columns=[column(0, "Column1", "guess", confidence=0.5)]))
    assert list(result.dataframe.columns) == ["Column1"]
    assert result.issues[0]["rule"] == "uncertain_schema"


def test_conditional_branch_columns_and_skipped_answers_remain_separate():
    df = pd.DataFrame(
        [["Developer", None], [None, "Analyst"]], columns=["Preferred Role", "Preferred Role 2"]
    )
    report = SchemaReport(
        columns=[
            column(0, "Preferred Role", "preferred_role", "categorical"),
            column(1, "Preferred Role 2", "preferred_role_2", "categorical"),
        ]
    )
    result = apply_schema(df, report)
    assert list(result.dataframe.columns) == ["preferred_role", "preferred_role_2"]
    assert result.dataframe.iloc[0, 1] is None
    assert result.dataframe.iloc[1, 0] is None
    assert not result.issues


def test_context_preserves_duplicate_column_positions_and_false():
    df = pd.DataFrame([[False, "   "], [False, None]], columns=["same", "same"])
    context = build_schema_context(df)
    assert context[0]["sample_values"] == ["False"]
    assert not context[0]["is_empty"] and context[1]["is_empty"]
    assert context[1]["column_index"] == 1


def prepared(values):
    return PreparedData(
        provenance="synthetic", columns=["التخصص", "other"], rows=[[v, "unchanged"] for v in values]
    )


class FakeCategories:
    def __init__(self, *, bad_batch=False):
        self.calls = []
        self.bad_batch = bad_batch

    def analyze(self, role, payload, response_type):
        self.calls.append(payload)
        rows = []
        for value in payload["values"]:
            canonical = "Computer Science" if value in {"علوم الحاسب", "CS"} else value
            status = "mapped" if canonical != value else "unchanged"
            if value == "ambiguous":
                canonical, status = None, "needs_review"
            rows.append(
                {
                    "original_value": value,
                    "column": payload["column"],
                    "category": payload["category"],
                    "canonical_value": canonical,
                    "confidence": 0.5 if status == "needs_review" else 0.95,
                    "status": status,
                    "reasoning": "Synthetic test",
                }
            )
        if self.bad_batch and len(self.calls) == 2:
            rows = []
        return CategoryReport(results=rows)


def test_categories_mapping_ambiguity_and_multiselect():
    data = prepared(["علوم الحاسب", "CS", "ambiguous", "Python, Java", None, "CS"])
    client = FakeCategories()
    result = run_categories(data, "التخصص", "Major", client)
    assert result.dataframe.iloc[:, 0].tolist() == [
        "Computer Science",
        "Computer Science",
        "ambiguous",
        "Python, Java",
        None,
        "Computer Science",
    ]
    assert result.dataframe["other"].tolist() == ["unchanged"] * 6
    assert data.rows[0][0] == "علوم الحاسب"
    assert len(client.calls) == 1 and client.calls[0]["values"].count("CS") == 1
    assert {issue["rule"] for issue in result.issues} == {
        "uncertain_category",
        "unsupported_scalar_value",
    }


def test_categories_missing_items_are_flagged():
    data = prepared([str(i) for i in range(21)])
    before = data.model_dump()
    client = FakeCategories(bad_batch=True)
    result = run_categories(data, "التخصص", "Major", client)
    assert sum(issue["rule"] == "missing_category_mapping" for issue in result.issues) == 10
    assert len(client.calls) == 3
    assert data.model_dump() == before


def test_text_preserves_language_short_answers_and_originals():
    df = pd.DataFrame(
        {
            "feedback": ["  مرحبا   Python\n! ", "no", "لا", "C", "لا يوجد", None, "  "],
            "id": ["001"] * 7,
        }
    )
    before = df.copy(deep=True)
    result = run_text(df, ["feedback"])
    assert result.dataframe["feedback_cleaned"].tolist() == [
        "مرحبا Python !",
        "no",
        "لا",
        "C",
        "",
        "",
        "",
    ]
    assert result.dataframe["feedback_missing"].tolist() == [False] * 4 + [True] * 3
    assert "feedback_sentiment" not in result.dataframe
    pd.testing.assert_frame_equal(df, before)
    pd.testing.assert_series_equal(result.dataframe["feedback"], df["feedback"])
    assert all(issue["applicability"] == "unknown" for issue in result.issues)


def test_text_enrichment_and_masking_are_opt_in():
    df = pd.DataFrame({"feedback": ["ممتاز demo@example.invalid"]})
    default = run_text(df, ["feedback"])
    masked = run_text(df, ["feedback"], enrich=True, mask_pii=True)
    assert "demo@example.invalid" in default.dataframe.at[0, "feedback_cleaned"]
    assert "[EMAIL_REDACTED]" in masked.dataframe.at[0, "feedback_cleaned"]
    assert "demo@example.invalid" in masked.dataframe.at[0, "feedback"]
    assert masked.dataframe.at[0, "feedback_sentiment"] == "Positive"
    assert not masked.details["fully_anonymized"]


def test_text_rejects_target_collisions():
    with pytest.raises(ValueError, match="already exist"):
        run_text(pd.DataFrame({"feedback": ["hi"], "feedback_cleaned": ["old"]}), ["feedback"])
    with pytest.raises(ValueError, match="exactly once"):
        run_text(pd.DataFrame([["x", "y"]], columns=["same", "same"]), ["same"])


def test_private_input_is_masked_locally():
    prepared, vault = prepare_private_data(pd.DataFrame({"Email": ["a@example.com"]}))
    assert prepared.rows == [["[PRIVATE_0_0]"]]
    assert vault.values[(0, 0)] == "a@example.com"


def test_private_preparation_serializes_excel_datetime():
    prepared, _vault = prepare_private_data(
        pd.DataFrame({"Timestamp": [datetime(2026, 9, 13, 10, 30)]})
    )
    assert prepared.rows == [["2026-09-13T10:30:00"]]
    with pytest.raises(TypeError, match="PreparedData"):
        run_schema(pd.DataFrame())
