"""Constrained model-planned cleanup with a deterministic, auditable executor."""

import re
from collections import Counter

import pandas as pd

from .contracts import AdaptivePlan, StageResult
from .model import LocalModel, ModelError

AUTOMATIC_OPERATIONS = {"literal_replace", "regex_replace", "normalize_whitespace"}
PROTECTED_COLUMN = re.compile(
    r"(?:name|email|phone|mobile|student|university_id|(?:^|_)id(?:_|$)|"
    r"الاسم|البريد|الجوال|الهاتف|الرقم)",
    re.I,
)
UNSAFE_REGEX = re.compile(r"\(\?[=!<]|\\[1-9]|\(\?P|\{\d{4,}(?:,\d*)?\}")


def structural_shape(value: object) -> str:
    """Expose punctuation and broad character classes without exposing cell contents."""
    if pd.isna(value):
        return "<EMPTY>"
    rendered = str(value)[:240]
    shaped = []
    for char in rendered:
        if char.isascii() and char.isalpha():
            token = "a"
        elif char.isdigit():
            token = "0"
        elif "\u0600" <= char <= "\u06ff":
            token = "ع"
        elif char.isspace():
            token = " "
        else:
            token = char
        if not shaped or token != shaped[-1] or token not in {"a", "0", "ع", " "}:
            shaped.append(token)
    return "".join(shaped)


def profile_dataframe(df: pd.DataFrame, *, samples_per_column: int = 12) -> list[dict]:
    profiles = []
    for position, column in enumerate(df.columns):
        values = [value for value in df.iloc[:, position] if not pd.isna(value) and str(value)]
        shapes = Counter(structural_shape(value) for value in values)
        profiles.append(
            {
                "column": str(column),
                "position": position,
                "nonempty": len(values),
                "distinct_shapes": len(shapes),
                "common_shapes": [
                    {"shape": shape, "count": count}
                    for shape, count in shapes.most_common(samples_per_column)
                ],
            }
        )
    return profiles


def _column_position(df: pd.DataFrame, name: str) -> int | None:
    matches = [i for i, column in enumerate(df.columns) if str(column) == name]
    return matches[0] if len(matches) == 1 else None


def _safe_regex(pattern: str) -> bool:
    if len(pattern) > 120 or UNSAFE_REGEX.search(pattern):
        return False
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True


def _apply_string_operation(value, operation):
    if not isinstance(value, str):
        return value
    if operation.operation == "literal_replace":
        return value.replace(operation.match, operation.replacement)
    if operation.operation == "regex_replace":
        return re.sub(operation.match, operation.replacement, value)
    if operation.operation == "normalize_whitespace":
        return re.sub(r"\s+", " ", value).strip()
    return value


def execute_plan(df: pd.DataFrame, plan: AdaptivePlan) -> StageResult:
    result = StageResult(df.copy(deep=True), "adaptive")
    decisions = []
    total_cells = max(df.shape[0] * max(df.shape[1], 1), 1)
    for index, operation in enumerate(plan.operations):
        decision = {
            "operation_index": index,
            "operation": operation.operation,
            "column": operation.column,
            "confidence": operation.confidence,
            "risk": operation.risk,
            "reason": operation.reason,
        }
        position = _column_position(result.dataframe, operation.column)
        reason = None
        if position is None:
            reason = "column_not_unique_or_missing"
        elif operation.operation not in AUTOMATIC_OPERATIONS:
            reason = "review_required"
        elif operation.risk != "low" or operation.confidence < 0.95:
            reason = "risk_or_confidence_threshold"
        elif operation.operation == "regex_replace" and not _safe_regex(operation.match):
            reason = "unsafe_regex"
        elif PROTECTED_COLUMN.search(operation.column) and operation.operation not in {
            "literal_replace",
            "normalize_whitespace",
        }:
            reason = "protected_column"
        if reason:
            decision.update({"status": "not_applied", "policy_reason": reason})
            decisions.append(decision)
            result.issues.append(
                {
                    "rule": "adaptive_operation_needs_review",
                    "operation_index": index,
                    "policy_reason": reason,
                }
            )
            continue

        before = result.dataframe.iloc[:, position].copy()
        after = before.map(lambda value: _apply_string_operation(value, operation))
        affected = [row for row, (old, new) in enumerate(zip(before, after)) if old != new]
        maximum = max(50, round(len(df) * 0.5))
        if len(affected) > maximum or (total_cells >= 200 and len(affected) > total_cells * 0.25):
            decision.update(
                {
                    "status": "not_applied",
                    "policy_reason": "change_limit",
                    "affected": len(affected),
                }
            )
            decisions.append(decision)
            result.issues.append(
                {
                    "rule": "adaptive_operation_needs_review",
                    "operation_index": index,
                    "policy_reason": "change_limit",
                    "affected": len(affected),
                }
            )
            continue
        result.dataframe.isetitem(position, after.astype(object))
        for row in affected:
            result.changes.append(
                {
                    "row_index": row,
                    "column_index": position,
                    "before": before.iloc[row],
                    "after": after.iloc[row],
                    "operation": operation.operation,
                    "operation_index": index,
                }
            )
        decision.update({"status": "applied", "affected": len(affected)})
        decisions.append(decision)
    result.details = {"summary": plan.summary, "decisions": decisions}
    return result


def run_adaptive(df: pd.DataFrame, *, model=None) -> StageResult:
    result = StageResult(df.copy(deep=True), "adaptive")
    client = model or LocalModel()
    payload = {
        "columns": [str(column) for column in df.columns],
        "profiles": profile_dataframe(df),
        "authority": "Propose only registered operations. Python policy decides execution.",
    }
    try:
        plan = client.analyze("adaptive", payload, AdaptivePlan)
    except ModelError as exc:
        result.issues.append({"rule": "adaptive_planner_failed", "message": str(exc)})
        result.details = {"planner_status": "failed"}
        return result
    return execute_plan(df, plan)
