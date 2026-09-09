"""Amirah's structured-data stage, integrated with shared results and privacy gates."""

import pandas as pd

from ..contracts import StageResult
from ..privacy import PreparedData, PrivacyNotReady
from ..structured.normalizers import blank, infer_supported_role
from ..structured.rules import RULES, normalize_value
from ..structured.university import build_university_map, surface_normalize


def selected_roles(df, column_roles):
    if column_roles is None:
        return {
            i: role for i, name in enumerate(df.columns) if (role := infer_supported_role(name))
        }
    roles = {}
    for name, role in column_roles.items():
        indices = [i for i, column in enumerate(df.columns) if column == name]
        if len(indices) != 1:
            raise ValueError("Each explicitly selected structured column must exist exactly once")
        if role not in {*RULES, "university"}:
            raise ValueError("Unsupported structured field role")
        roles[indices[0]] = role
    return roles


def changed(before, after):
    if blank(before) and blank(after):
        return False
    return str(before) != str(after) or isinstance(before, str) != isinstance(after, str)


def run_structured_many(tables, column_roles=None, *, judge_universities=False, model=None):
    """Normalize a named set of dataframes with shared observed university spellings.

    Explicit roles select only those fields; otherwise use conservative header aliases.
    For Qwen-assisted university proposals, every table must be PreparedData.
    """
    if judge_universities and any(not isinstance(table, PreparedData) for table in tables.values()):
        raise PrivacyNotReady(
            "University model assistance requires prepared synthetic/sanitized input"
        )
    results, roles_by_file, universities = {}, {}, []
    for name, table in tables.items():
        df = table.dataframe() if isinstance(table, PreparedData) else table
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Structured input must be a dataframe or PreparedData")
        result = StageResult(df.copy(deep=True), "structured")
        roles = selected_roles(df, column_roles)
        roles_by_file[name] = roles
        result.details = {
            "column_roles": {str(i): role for i, role in roles.items()},
            "university_model_assistance": judge_universities,
        }
        if isinstance(table, PreparedData):
            result.details["input_provenance"] = table.provenance
        if not roles:
            result.issues.append(
                {"rule": "no_supported_columns", "message": "Supply explicit --field mappings"}
            )
        for i, role in roles.items():
            if role == "university":
                universities.extend(df.iloc[:, i].tolist())
                continue
            # Object storage avoids coercing bools back to numeric or strings to float.
            result.dataframe.isetitem(i, df.iloc[:, i].astype(object).copy())
            for row, value in enumerate(df.iloc[:, i]):
                normalized = normalize_value(value, role)
                if normalized.issue:
                    result.issues.append(
                        {
                            "row_index": row,
                            "column_index": i,
                            "role": role,
                            "rule": normalized.issue,
                        }
                    )
                if changed(value, normalized.value):
                    result.dataframe.iat[row, i] = normalized.value
                    result.changes.append(
                        {
                            "row_index": row,
                            "column_index": i,
                            "role": role,
                            "before": value,
                            "after": normalized.value,
                        }
                    )
        results[name] = result
    mapping, proposals, limited = build_university_map(
        universities, judge=judge_universities, model=model
    )
    for name, result in results.items():
        for i, role in roles_by_file[name].items():
            if role != "university":
                continue
            result.dataframe.isetitem(i, result.dataframe.iloc[:, i].astype(object).copy())
            for row, value in enumerate(result.dataframe.iloc[:, i].tolist()):
                if blank(value):
                    continue
                if not isinstance(value, str):
                    result.issues.append(
                        {"row_index": row, "column_index": i, "rule": "invalid_university"}
                    )
                    continue
                normalized = mapping.get(surface_normalize(value), value)
                if changed(value, normalized):
                    result.dataframe.iat[row, i] = normalized
                    result.changes.append(
                        {
                            "row_index": row,
                            "column_index": i,
                            "role": role,
                            "before": value,
                            "after": normalized,
                        }
                    )
        if "university" in roles_by_file[name].values():
            result.details["university_proposals"] = proposals
            if proposals:
                result.issues.append(
                    {"rule": "university_equivalence_requires_review", "count": len(proposals)}
                )
            if limited:
                result.issues.append(
                    {
                        "rule": "university_candidate_limit",
                        "message": "Candidate review was limited to 100 distinct names and 200 comparisons",
                    }
                )
    return results


def run_structured(data, column_roles=None, *, judge_universities=False, model=None):
    return run_structured_many(
        {"input": data}, column_roles, judge_universities=judge_universities, model=model
    )["input"]
