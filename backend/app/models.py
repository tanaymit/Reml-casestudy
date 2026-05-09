from decimal import Decimal
from typing import Optional
from datetime import date
from pydantic import BaseModel, field_validator, model_validator


class TargetAsset(BaseModel):
    address: str
    submarket: str
    total_sf: int
    year_built: int
    clear_height_ft: int
    as_of: date

    @field_validator("total_sf", "year_built", "clear_height_ft")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be a positive integer")
        return v

    @model_validator(mode="after")
    def sane_year(self) -> "TargetAsset":
        if not (1900 <= self.year_built <= 2030):
            raise ValueError("year_built must be between 1900 and 2030")
        return self


class WaterfallStep(BaseModel):
    step: str
    before: Decimal
    after: Decimal
    delta: Decimal
    delta_pct: Decimal
    rationale: str


class CompRecord(BaseModel):
    id: str
    address: str
    submarket: str
    signed_date: str
    lease_sf: Optional[int]
    rent_psf_yr: Optional[Decimal]
    year_built: Optional[int]
    clear_height_ft: Optional[int]
    source: str
    confidence: Optional[float]
    status: str
    drop_reason: Optional[str]
    is_monthly_converted: bool


class RentEstimate(BaseModel):
    point_estimate_psf_yr: Decimal
    low: Decimal
    high: Decimal
    confidence: Decimal
    comp_count_used: int
    comp_count_dropped: int
    waterfall: list[WaterfallStep]
    comps_used: list[CompRecord]
    comps_dropped: list[CompRecord]
