import pandas as pd

from data_cleaning_agent.contracts import CategoryReport, SchemaReport
from data_cleaning_agent.pipeline import (
    _remove_embedded_headers,
    _remove_padding_rows,
    _trim_scalar_whitespace,
    run_pipeline,
)


class PipelineModel:
    def analyze(self, role, payload, response_type):
        if role == "schema":
            names = ["email", "phone", "major", "feedback"]
            kinds = ["email", "phone", "categorical", "free_text"]
            return SchemaReport(
                columns=[
                    {
                        "column_index": item["column_index"],
                        "original_name": item["column_name"],
                        "canonical_name": names[item["column_index"]],
                        "column_type": kinds[item["column_index"]],
                        "confidence": 0.99,
                    }
                    for item in payload
                ]
            )
        assert role == "categories" and response_type is CategoryReport
        return CategoryReport(
            results=[
                {
                    "original_value": value,
                    "column": payload["column"],
                    "category": payload["category"],
                    "canonical_value": "Computer Science",
                    "confidence": 0.95,
                    "status": "mapped",
                    "reasoning": "synthetic",
                }
                for value in payload["values"]
            ]
        )


def test_full_pipeline_masks_model_input_and_preserves_source(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text(
        "E-mail,Phone Number,Major,Feedback\na@x.com,0551234567,CS,  good  \n", encoding="utf-8"
    )
    output = tmp_path / "out"
    events = []
    summary = run_pipeline(source, output, model=PipelineModel(), progress=events.append)
    assert summary["processed_tables"] == 1 and summary["failed_tables"] == 0
    result = pd.read_csv(next(output.glob("*.cleaned.csv")), dtype=str)
    assert result.loc[0, "email"] == "a@x.com"
    assert result.loc[0, "phone"] == "+966551234567"
    assert result.loc[0, "major"] == "Computer Science"
    assert result.loc[0, "feedback"] == "good"
    assert source.read_text(encoding="utf-8").startswith("E-mail")
    assert [event["stage"] for event in events] == [
        "reading",
        "schema",
        "structured",
        "categories",
        "text",
        "validation",
        "complete",
    ]
    assert list(result.columns) == ["email", "phone", "major", "feedback"]


def test_repeated_form_headers_are_removed_without_matching_normal_rows():
    frame = pd.DataFrame(
        [
            ["الجنس", "رقم الجوال", "اسم الجامعة", "التخصص الجامعي"],
            ["Female", "0500000000", "UJ", "CS"],
        ],
        columns=["gender", "phone", "university", "major"],
    )
    cleaned, stage = _remove_embedded_headers(frame)
    assert len(cleaned) == 1
    assert cleaned.iloc[0].tolist() == ["Female", "0500000000", "UJ", "CS"]
    assert stage.details["removed_rows"] == [0]
    assert not stage.issues


def test_padding_rows_are_removed_and_scalar_whitespace_is_trimmed():
    frame = pd.DataFrame(
        {
            "name": ["  Ahmed  ", None, None, None],
            "email": ["a@example.com ", None, None, None],
            "day_1": [True, False, "Absent", None],
        }
    )
    cleaned, padding = _remove_padding_rows(frame)
    cleaned, whitespace = _trim_scalar_whitespace(cleaned)
    assert len(cleaned) == 1
    assert cleaned.iloc[0].tolist() == ["Ahmed", "a@example.com", True]
    assert padding.details["reasons"] == {
        1: "status_only_padding",
        2: "status_only_padding",
        3: "blank_row",
    }
    assert len(whitespace.changes) == 2
