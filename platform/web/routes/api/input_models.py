"""Input validation models for API routes.

All POST/PATCH JSON endpoints should use these models as Body parameters
to get automatic type checking, length limits, and 422 error responses.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ── Memory ────────────────────────────────────────────────────────


class GlobalMemoryCreate(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="general", max_length=50)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# ── Guidelines ────────────────────────────────────────────────────


class GuidelineItem(BaseModel):
    category: str = Field(default="must_use", max_length=100)
    topic: str = Field(min_length=1, max_length=300)
    constraint: str = Field(min_length=1, max_length=1000)


class GuidelineSyncRequest(BaseModel):
    source: str = Field(default="manual", pattern=r"^(confluence|manual)$")
    domain: str = Field(min_length=1, max_length=100)
    # Confluence-specific
    url: Optional[str] = Field(default=None, max_length=500)
    token: Optional[str] = Field(default=None, max_length=500)
    space: Optional[str] = Field(default=None, max_length=100)
    # Manual-specific
    items: Optional[list[GuidelineItem]] = Field(default=None, max_length=500)

    @field_validator("url", mode="before")
    @classmethod
    def url_strip(cls, v):
        return v.strip() if v else v

    @field_validator("domain", mode="before")
    @classmethod
    def domain_strip(cls, v):
        return v.strip() if v else v


# ── Incidents ─────────────────────────────────────────────────────


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    severity: str = Field(default="P3", pattern=r"^P[0-4]$")
    source: str = Field(default="manual", max_length=100)
    error_type: str = Field(default="", max_length=200)
    error_detail: str = Field(default="", max_length=2000)
    mission_id: str = Field(default="", max_length=100)
    agent_id: str = Field(default="", max_length=100)


class IncidentUpdate(BaseModel):
    status: Optional[str] = Field(
        default=None, pattern=r"^(open|investigating|resolved|closed)$"
    )
    resolution: Optional[str] = Field(default=None, max_length=2000)


# ── Integrations ──────────────────────────────────────────────────


class IntegrationUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class IntegrationTestRequest(BaseModel):
    config: Optional[dict[str, Any]] = None


# ── Teams ─────────────────────────────────────────────────────────


class TeamChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = Field(default=None, max_length=100)
