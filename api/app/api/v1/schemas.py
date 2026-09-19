from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchResponse(BaseModel):
    query: str
    page: str
    pillars: list[str]
    topics: list[str]
    sdgs: list[int]
    years: list[str] | None
    matched: bool
    explanation: str


class ReportRequest(BaseModel):
    mode: str = Field(pattern="^(impact|impact-sdgs|sdgs)$")
    year_from: str | None = Field(default=None, pattern=r"^\d{4}$")
    year_to: str | None = Field(default=None, pattern=r"^\d{4}$")
    pillars: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    sdgs: list[int] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str


class AnalyticsResponse(BaseModel):
    mode: str
    filters: dict[str, Any]
    data_as_of: str | None
    summary: dict[str, Any]
    narrative: str
    charts: dict[str, Any]
    tables: dict[str, Any]
    caveats: list[str]
