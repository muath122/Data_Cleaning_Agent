"""Validated model responses and the shared stage result contract."""

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ColumnMapping(StrictModel):
    column_index: int = Field(ge=0)
    original_name: str
    canonical_name: str | None = Field(pattern=r"^[a-z][a-z0-9_]*$")
    column_type: Literal[
        "name",
        "email",
        "phone",
        "datetime",
        "integer",
        "float",
        "boolean",
        "categorical",
        "multi_select",
        "free_text",
        "identifier",
        "url",
        "string",
        "empty",
        "other",
    ]
    confidence: float = Field(ge=0, le=1)


class SchemaReport(StrictModel):
    columns: list[ColumnMapping]


Category = Literal[
    "Major", "Committee", "Skills", "Tools", "Programming languages", "Roles", "Departments"
]


class CategoryMapping(StrictModel):
    original_value: str
    column: str
    category: Category
    canonical_value: str | None
    confidence: float = Field(ge=0, le=1)
    status: Literal["mapped", "unchanged", "needs_review"]
    reasoning: str

    @model_validator(mode="after")
    def consistent_status(self):
        if self.status == "needs_review":
            if self.canonical_value is not None:
                raise ValueError("needs_review must have a null canonical value")
        elif not self.canonical_value or not self.canonical_value.strip():
            raise ValueError("Accepted mappings require a nonempty canonical value")
        if self.status == "unchanged" and self.canonical_value != self.original_value:
            raise ValueError("unchanged must preserve the original value")
        return self


class CategoryReport(StrictModel):
    results: list[CategoryMapping]


@dataclass
class StageResult:
    """References are zero-based source positions. Reports can contain private values."""

    dataframe: pd.DataFrame
    stage: str
    changes: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    def report(self) -> dict:
        return {
            "stage": self.stage,
            "status": "needs_review" if self.issues else "completed",
            "pipeline_validated": False,
            "rows": len(self.dataframe),
            "columns": len(self.dataframe.columns),
            "changes": self.changes,
            "issues": self.issues,
            "details": self.details,
        }
