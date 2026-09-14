import pandas as pd

from data_cleaning_agent.contracts import CategoryReport, SchemaReport
from data_cleaning_agent.pipeline import run_pipeline


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
    assert result.loc[0, "feedback_cleaned"] == "good"
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
