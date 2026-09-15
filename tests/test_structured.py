import zipfile
from datetime import datetime, timezone
from io import BytesIO

import openpyxl
import pandas as pd
import pytest

from data_cleaning_agent.cli import main
from data_cleaning_agent.contracts import UniversityJudgment
from data_cleaning_agent.model import ModelError
from data_cleaning_agent.privacy import PreparedData, PrivacyNotReady
from data_cleaning_agent.stages.structured import run_structured, run_structured_many
from data_cleaning_agent.structured.batch import load_excel_files, process_input
from data_cleaning_agent.structured.rules import normalize_value


@pytest.mark.parametrize(
    "value",
    [
        "0551234567",
        "966551234567",
        "+966 (55) 123-4567",
        "00966551234567",
        "٥٥١٢٣٤٥٦٧",
        551234567,
        551234567.0,
    ],
)
def test_saudi_phone_formats(value):
    result = normalize_value(value, "phone")
    assert result.value == "+966551234567" and result.issue is None


@pytest.mark.parametrize(
    "role,value",
    [
        ("phone", "call 0551234567"),
        ("phone", "+15551234567"),
        ("phone", 55.12),
        ("email", "first last@example.com"),
        ("email", 123),
        ("academic_level", "21"),
        ("academic_level", "3.5"),
        ("academic_level", "Year 2"),
        ("academic_level", "Level 2 or 3"),
        ("academic_level", "المستوى الثاني والثالث"),
        ("timestamp", 45000),
        ("timestamp", "03/04/2026"),
        ("timestamp", "2026-02-30"),
        ("gender", "prefer not to say"),
        ("boolean", "sometimes"),
        ("university_id", 123.5),
        ("university_id", "00 123"),
    ],
)
def test_ambiguous_values_are_preserved_for_review(role, value):
    result = normalize_value(value, role)
    assert result.value == value and result.issue


@pytest.mark.parametrize("value,expected", [("  User@EXAMPLE.COM  ", "User@example.com")])
def test_email_keeps_local_part_case(value, expected):
    assert normalize_value(value, "email").value == expected


@pytest.mark.parametrize(
    "value,expected", [("٠٠١٢٣", "00123"), ("abC123", "abC123"), (123.0, "123")]
)
def test_identifiers(value, expected):
    result = normalize_value(value, "university_id")
    assert result.value == expected
    assert bool(result.issue) == (not isinstance(value, str))


@pytest.mark.parametrize(
    "value,expected",
    [
        ("المستوى الثاني", "Level 2"),
        ("الأول", "Level 1"),
        (10.0, "Level 10"),
        (12, "Level 12"),
        ("Level 3", "Level 3"),
    ],
)
def test_academic_level(value, expected):
    assert normalize_value(value, "academic_level").value == expected


def test_dates_preserve_timezone_and_precision():
    value = datetime(2026, 9, 9, 12, 0, 0, 123456, tzinfo=timezone.utc)
    assert normalize_value(value, "timestamp").value == "2026-09-09 12:00:00.123456+00:00"
    assert normalize_value("2026-09-09T12:00:00Z", "timestamp").value == "2026-09-09 12:00:00+00:00"


@pytest.mark.parametrize(
    "value,expected",
    [(True, "Present"), (False, "Absent"), (0.0, "Absent"), ("متأخر", "Late"), ("بعذر", "Excused")],
)
def test_attendance(value, expected):
    assert normalize_value(value, "attendance").value == expected


def test_stage_preserves_columns_rows_blanks_and_unrelated_values():
    df = pd.DataFrame(
        {
            "phone_2": ["0551234567", None],
            "personal_email": ["A@EXAMPLE.COM", None],
            "university_email": ["B@EXAMPLE.COM", None],
            "gender": ["ذكر", "أنثى"],
            "attendance": [True, False],
            "arbitrary_id": [0, 1],
            "notes": ["yes", "no"],
        }
    )
    before = df.copy(deep=True)
    result = run_structured(df)
    pd.testing.assert_frame_equal(df, before)
    assert list(result.dataframe.columns) == list(df.columns)
    assert len(result.dataframe) == 2
    assert result.dataframe.at[1, "phone_2"] is None
    assert result.dataframe.at[0, "phone_2"] == "+966551234567"
    assert result.dataframe["gender"].tolist() == ["Male", "Female"]
    assert result.dataframe["attendance"].tolist() == ["Present", "Absent"]
    pd.testing.assert_series_equal(df["arbitrary_id"], result.dataframe["arbitrary_id"])
    pd.testing.assert_series_equal(df["notes"], result.dataframe["notes"])
    assert result.changes[0]["row_index"] == 0
    assert not result.report()["pipeline_validated"]


@pytest.mark.parametrize("value,expected", [("Male | رجل", "Male"), ("Female | أنثى", "Female")])
def test_bilingual_gender_labels(value, expected):
    assert normalize_value(value, "gender").value == expected


def test_explicit_roles_and_no_content_based_boolean_guess():
    df = pd.DataFrame({"consent?": ["yes", "no"], "phone": ["0551234567", None]})
    result = run_structured(df, {"consent?": "boolean"})
    assert result.dataframe["consent?"].tolist() == [True, False]
    assert result.dataframe.at[0, "phone"] == "0551234567"
    with pytest.raises(ValueError):
        run_structured(df, {"missing": "boolean"})
    with pytest.raises(ValueError):
        run_structured(df, {"phone": "unknown"})
    duplicates = pd.DataFrame([["yes", "no"]], columns=["same", "same"])
    with pytest.raises(ValueError):
        run_structured(duplicates, {"same": "boolean"})


def test_cross_file_universities_merge_only_case_whitespace():
    tables = {
        "a": pd.DataFrame({"university": ["example university", "Example University North"]}),
        "b": pd.DataFrame({"university": [" Example   University ", "Example University South"]}),
    }
    result = run_structured_many(tables)
    assert result["a"].dataframe.at[0, "university"] == result["b"].dataframe.at[0, "university"]
    assert result["a"].dataframe.at[1, "university"] != result["b"].dataframe.at[1, "university"]
    assert result["a"].details["university_proposals"]
    assert all(not p["applied"] for p in result["a"].details["university_proposals"])


class UniversityModel:
    def __init__(self, bad=False):
        self.bad = bad
        self.calls = []

    def analyze(self, role, payload, response_type):
        self.calls.append(payload)
        assert role == "structured" and response_type is UniversityJudgment
        return UniversityJudgment(
            value_a="wrong" if self.bad else payload["value_a"],
            value_b=payload["value_b"],
            same_university=True,
            confidence=0.99,
            reasoning="Test proposal",
        )


def test_university_qwen_requires_prepared_input_and_returns_proposals():
    df = pd.DataFrame({"university": ["Example University", "جامعة مثال"]})
    client = UniversityModel()
    with pytest.raises(PrivacyNotReady):
        run_structured(df, judge_universities=True, model=client)
    assert not client.calls
    prepared = PreparedData(provenance="synthetic", columns=["university"], rows=df.values.tolist())
    result = run_structured(prepared, judge_universities=True, model=client)
    assert len(set(result.dataframe["university"])) == 2
    assert result.details["university_proposals"][0]["same_university"] is True
    with pytest.raises(ModelError):
        run_structured(prepared, judge_universities=True, model=UniversityModel(bad=True))


def test_university_knowledge_base_unifies_case_and_language():
    df = pd.DataFrame({"university": ["UJ", "uj", "Uj", "جامعة جدة", "Jeddah University"]})
    result = run_structured(df)
    assert result.dataframe["university"].tolist() == ["University of Jeddah"] * 5


def excel_bytes():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["phone", "university_id", "attendance"])
    sheet.append(["0551234567", "00123", True])
    sheet.append([None, None, False])
    out = BytesIO()
    workbook.save(out)
    workbook.close()
    return out.getvalue()


def test_batch_zip_does_not_extract_paths_or_lose_same_basenames(tmp_path):
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("a/responses.xlsx", excel_bytes())
        archive.writestr("b/responses.xlsx", excel_bytes())
        archive.writestr("../../outside.txt", "must not be extracted")
    out = tmp_path / "result"
    archive_path, results = process_input(source, out)
    assert len(results) == 2
    assert results["a/responses.xlsx"].dataframe.at[0, "university_id"] == "00123"
    with zipfile.ZipFile(archive_path) as archive:
        assert sorted(archive.namelist()) == ["0001.structured.xlsx", "0002.structured.xlsx"]
    with pytest.raises(FileExistsError):
        process_input(source, out)
    assert archive_path.exists()
    assert not (tmp_path / "outside.txt").exists()
    assert not (tmp_path / ".input_extracted").exists()


def test_batch_folder_preserves_relative_names_and_rejects_empty(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    with pytest.raises(ValueError, match="No Excel"):
        load_excel_files(source)
    for name in ["a", "b"]:
        folder = source / name
        folder.mkdir()
        (folder / "same.xlsx").write_bytes(excel_bytes())
    assert set(load_excel_files(source)) == {"a/same.xlsx", "b/same.xlsx"}
    with pytest.raises(ValueError, match="outside"):
        process_input(source, source / "output")


def test_structured_cli_raw_and_model_gate(tmp_path, capsys):
    source = tmp_path / "source.csv"
    source.write_text("phone,consent?\n0551234567,yes\n", encoding="utf-8")
    assert (
        main(["stage", "structured", "--input", str(source), "--output", str(tmp_path / "out.csv")])
        == 0
    )
    assert (tmp_path / "out.structured.csv").exists()
    capsys.readouterr()
    assert not (tmp_path / "blocked.structured.csv").exists()
