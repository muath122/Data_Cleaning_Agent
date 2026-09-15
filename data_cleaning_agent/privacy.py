"""Local, reversible masking used before any dataframe content reaches Qwen."""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import Field, model_validator

from .contracts import StrictModel


class PrivacyNotReady(RuntimeError):
    pass


class PreparedData(StrictModel):
    """Caller attestation, NOT an automatic proof that a payload is anonymous."""

    provenance: Literal["synthetic", "manually_sanitized", "locally_pseudonymized"]
    columns: list[str] = Field(min_length=1)
    rows: list[list[str | int | float | bool | None]]

    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Each row must match the column count")
        return self

    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=self.columns, dtype=object)


def read_prepared(path: str | Path) -> PreparedData:
    # Reject nonstandard NaN/Infinity JSON, which would break model request encoding.
    def invalid_constant(value):
        raise ValueError("Prepared JSON cannot contain NaN or Infinity")

    payload = json.loads(
        Path(path).read_text(encoding="utf-8-sig"), parse_constant=invalid_constant
    )
    return PreparedData.model_validate(payload)


@dataclass
class PrivacyVault:
    """In-memory coordinate map. It is never included in model payloads or reports."""

    values: dict[tuple[int, int], object]


DIRECT_HEADER = re.compile(
    r"(?:name|email|e-mail|phone|mobile|university\s*id|student\s*id|"
    r"الاسم|البريد|الجوال|الهاتف|الرقم\s*الجامعي)",
    re.I,
)
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
PHONE_OR_ID = re.compile(r"(?<!\w)(?:\+?966|0)?5\d{8}(?!\w)|(?<!\w)\d{10,}(?!\w)")


def prepare_private_data(dataframe: pd.DataFrame) -> tuple[PreparedData, PrivacyVault]:
    """Mask direct-identifier columns and identifier patterns, preserving semantics elsewhere."""
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError("Privacy preparation requires a dataframe")
    clean = dataframe.copy(deep=True).astype(object)
    vault: dict[tuple[int, int], object] = {}
    for col, name in enumerate(clean.columns):
        direct = bool(DIRECT_HEADER.search(str(name)))
        for row, value in enumerate(clean.iloc[:, col].tolist()):
            if pd.isna(value) or (isinstance(value, str) and not value.strip()):
                continue
            rendered = str(value)
            masked = EMAIL.sub("[EMAIL]", rendered)
            masked = PHONE_OR_ID.sub("[IDENTIFIER]", masked)
            if direct:
                masked = f"[PRIVATE_{col}_{row}]"
            if masked != rendered:
                vault[(row, col)] = value
                clean.iat[row, col] = masked
            elif isinstance(value, (datetime, date)):
                clean.iat[row, col] = value.isoformat()
            elif not isinstance(value, (str, int, float, bool)):
                clean.iat[row, col] = rendered
    rows = clean.where(pd.notna(clean), None).values.tolist()
    return PreparedData(
        provenance="locally_pseudonymized",
        columns=[str(column) for column in clean.columns],
        rows=rows,
    ), PrivacyVault(vault)


def restore_identities(dataframe: pd.DataFrame, vault: PrivacyVault) -> pd.DataFrame:
    restored = dataframe.copy(deep=True).astype(object)
    for (row, col), value in vault.values.items():
        if row < len(restored) and col < len(restored.columns):
            restored.iat[row, col] = value
    return restored
