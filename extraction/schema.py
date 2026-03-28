from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExtractionStatus = Literal["confident", "partial_answer", "ambiguous", "no_answer"]
PlanType = Literal["DIRECT", "REGULAR"]


class ExtractedTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str | None = None
    amount: float | None = None
    extraction_status: ExtractionStatus = "no_answer"

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("date must use YYYY-MM-DD")
        return value


class ExtractedHolding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_name: str
    weight: float | None = None


class ExtractedFund(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fund_name: str
    plan_type: PlanType | None = None
    expense_ratio: float | None = None
    transactions: list[ExtractedTransaction] = Field(default_factory=list)
    holdings: list[ExtractedHolding] = Field(default_factory=list)
    current_value: float | None = None

    @field_validator("fund_name")
    @classmethod
    def normalize_fund_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("fund_name cannot be empty")
        return cleaned


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funds: list[ExtractedFund] = Field(default_factory=list)
