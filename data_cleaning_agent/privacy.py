"""Explicit boundary while automatic identity masking/restoration is unfinished."""

import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import Field, model_validator

from .contracts import StrictModel


class PrivacyNotReady(RuntimeError):
    pass


class PreparedData(StrictModel):
    """Caller attestation, NOT an automatic proof that a payload is anonymous."""

    provenance: Literal["synthetic", "manually_sanitized"]
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


def prepare_private_data(dataframe: pd.DataFrame) -> PreparedData:
    raise PrivacyNotReady(
        "Automatic privacy preparation/restoration is not implemented. "
        "Model stages require --sanitized-input with synthetic or manually sanitized JSON. "
        "Do not relabel raw applicant data as sanitized."
    )


def restore_identities(*args, **kwargs):
    raise PrivacyNotReady("Local identity restoration is not implemented")
