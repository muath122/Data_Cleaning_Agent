import pandas as pd

from data_cleaning_agent.adaptive import execute_plan, profile_dataframe, run_adaptive
from data_cleaning_agent.contracts import AdaptivePlan


def operation(**overrides):
    payload = {
        "operation": "literal_replace",
        "column": "email",
        "match": "\\@",
        "replacement": "@",
        "confidence": 0.99,
        "risk": "low",
        "reason": "escaped delimiter",
    }
    payload.update(overrides)
    return payload


def test_structural_profile_hides_private_content_but_preserves_artifacts():
    frame = pd.DataFrame({"email": [r"ahmed\@gm", "other@example.com"]})
    rendered = str(profile_dataframe(frame))
    assert "ahmed" not in rendered and "example" not in rendered
    assert r"\@" in rendered


def test_low_risk_literal_plan_executes_and_audits_changes():
    frame = pd.DataFrame({"email": [r"ahmed\@gm", "valid@example.com"]})
    plan = AdaptivePlan(summary="escaped at sign", operations=[operation()])
    result = execute_plan(frame, plan)
    assert result.dataframe.loc[0, "email"] == "ahmed@gm"
    assert result.dataframe.loc[1, "email"] == "valid@example.com"
    assert result.changes[0]["before"] == r"ahmed\@gm"
    assert result.details["decisions"][0]["status"] == "applied"


def test_semantic_or_destructive_plan_requires_review():
    frame = pd.DataFrame({"email": ["ahmed@gm"]})
    plan = AdaptivePlan(
        summary="guess a domain",
        operations=[operation(match="@gm", replacement="@gmail.com", risk="medium")],
    )
    result = execute_plan(frame, plan)
    assert result.dataframe.equals(frame)
    assert result.issues[0]["policy_reason"] == "risk_or_confidence_threshold"


def test_regex_cannot_run_on_protected_identifier_column():
    frame = pd.DataFrame({"student_id": ["12-34"]})
    plan = AdaptivePlan(
        summary="identifier rewrite",
        operations=[
            operation(
                operation="regex_replace",
                column="student_id",
                match="-",
                replacement="",
            )
        ],
    )
    result = execute_plan(frame, plan)
    assert result.dataframe.equals(frame)
    assert result.issues[0]["policy_reason"] == "protected_column"


class PlannerModel:
    def analyze(self, role, payload, response_type):
        assert role == "adaptive"
        assert "ahmed" not in str(payload)
        return response_type(summary="escaped at sign", operations=[operation()])


def test_adaptive_planner_receives_only_structural_profiles():
    frame = pd.DataFrame({"email": [r"ahmed\@gm"]})
    result = run_adaptive(frame, model=PlannerModel())
    assert result.dataframe.loc[0, "email"] == "ahmed@gm"
