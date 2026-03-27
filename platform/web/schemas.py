"""OpenAPI/Swagger schemas for Software Factory API."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional


# ── Health ──

class HealthResponse(BaseModel):
    status: str = Field(example="ok")
    detail: Optional[str] = None


# ── Projects ──

class ProjectOut(BaseModel):
    id: str
    name: str
    path: Optional[str] = ""
    factory_type: Optional[str] = ""
    domains: Optional[list[str]] = []
    lead_agent_id: Optional[str] = ""
    status: Optional[str] = "active"
    has_vision: Optional[bool] = False
    values: Optional[list[str]] = []

    class Config:
        json_schema_extra = {"example": {
            "id": "my-app", "name": "My App", "path": "/src/my-app",
            "factory_type": "standalone", "status": "active",
        }}


class ProjectCreate(BaseModel):
    id: Optional[str] = ""
    name: str
    path: Optional[str] = ""
    description: Optional[str] = ""
    factory_type: Optional[str] = "standalone"
    lead_agent_id: Optional[str] = "brain"
    values: Optional[str] = "quality,feedback"


# ── Missions / Epics ──

class MissionOut(BaseModel):
    id: str
    name: str
    project_id: Optional[str] = ""
    status: Optional[str] = "draft"
    type: Optional[str] = "epic"
    phases_total: Optional[int] = 0
    phases_done: Optional[int] = 0
    current_phase: Optional[str] = ""
    run_status: Optional[str] = ""


class MissionDetail(BaseModel):
    id: str
    name: str
    project_id: Optional[str] = ""
    status: Optional[str] = "draft"
    type: Optional[str] = "epic"
    wsjf_score: Optional[float] = 0
    business_value: Optional[int] = 0
    time_criticality: Optional[int] = 0
    risk_reduction: Optional[int] = 0
    job_duration: Optional[int] = 1


class MissionListResponse(BaseModel):
    missions: list[MissionOut]
    total: int


class MissionCreate(BaseModel):
    name: str
    project_id: Optional[str] = ""
    type: Optional[str] = "epic"
    description: Optional[str] = ""


class WsjfUpdate(BaseModel):
    business_value: int = Field(ge=1, le=10, example=8)
    time_criticality: int = Field(ge=1, le=10, example=5)
    risk_reduction: int = Field(ge=1, le=10, example=3)
    job_duration: int = Field(ge=1, le=10, example=2)


# ── Features ──

class FeatureOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    epic_id: Optional[str] = ""
    status: Optional[str] = "backlog"
    story_points: Optional[int] = 0
    assigned_to: Optional[str] = ""
    created_at: Optional[str] = ""
    priority: Optional[int] = 5


class FeatureCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    story_points: Optional[int] = 0
    priority: Optional[int] = 5


class FeatureUpdate(BaseModel):
    status: Optional[str] = None
    story_points: Optional[int] = None
    priority: Optional[int] = None
    assigned_to: Optional[str] = None


# ── User Stories ──

class StoryOut(BaseModel):
    id: str
    feature_id: Optional[str] = ""
    title: str
    description: Optional[str] = ""
    story_points: Optional[int] = 0
    status: Optional[str] = "backlog"
    sprint_id: Optional[str] = ""
    acceptance_criteria: Optional[str] = ""
    priority: Optional[int] = 5


class StoryCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    story_points: Optional[int] = 0
    acceptance_criteria: Optional[str] = ""
    priority: Optional[int] = 5


class StoryUpdate(BaseModel):
    status: Optional[str] = None
    story_points: Optional[int] = None
    sprint_id: Optional[str] = None
    title: Optional[str] = None


# ── Sprints ──

class SprintOut(BaseModel):
    id: str
    mission_id: Optional[str] = ""
    number: Optional[int] = 1
    name: str
    status: Optional[str] = "planning"
    velocity: Optional[int] = 0
    planned_sp: Optional[int] = 0


class SprintCreate(BaseModel):
    name: Optional[str] = ""
    goal: Optional[str] = ""


# ── Agents ──

class AgentOut(BaseModel):
    id: str
    name: str
    role: Optional[str] = ""
    provider: Optional[str] = ""
    model: Optional[str] = ""
    description: Optional[str] = ""
    icon: Optional[str] = ""
    color: Optional[str] = ""
    tags: Optional[list[str]] = []
    is_builtin: Optional[bool] = False


class AgentDetail(BaseModel):
    id: str
    name: str
    role: Optional[str] = ""
    provider: Optional[str] = ""
    model: Optional[str] = ""
    description: Optional[str] = ""
    system_prompt: Optional[str] = ""
    tools: Optional[list[str]] = []
    skills: Optional[list[str]] = []
    config: Optional[dict[str, Any]] = {}


# ── Sessions ──

class SessionOut(BaseModel):
    id: str
    name: Optional[str] = ""
    status: Optional[str] = "active"
    project_id: Optional[str] = ""
    goal: Optional[str] = ""
    created_at: Optional[str] = ""


# ── Incidents ──

class IncidentOut(BaseModel):
    id: str
    title: str
    severity: Optional[str] = "P3"
    status: Optional[str] = "open"
    source: Optional[str] = ""
    error_type: Optional[str] = ""
    error_detail: Optional[str] = ""
    mission_id: Optional[str] = ""
    agent_id: Optional[str] = ""
    resolution: Optional[str] = ""
    created_at: Optional[str] = ""
    resolved_at: Optional[str] = None


class IncidentCreate(BaseModel):
    title: str
    severity: Optional[str] = "P3"
    source: Optional[str] = "manual"
    error_type: Optional[str] = ""
    error_detail: Optional[str] = ""
    mission_id: Optional[str] = ""
    agent_id: Optional[str] = ""


class IncidentStats(BaseModel):
    open: int = 0
    resolved: int = 0
    closed: int = 0
    total: int = 0
    by_severity: Optional[dict[str, int]] = {}
    mttr_minutes: Optional[float] = 0


# ── LLM ──

class LlmStatsResponse(BaseModel):
    total_calls: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    by_provider: Optional[dict] = {}
    by_model: Optional[dict] = {}


class LlmProvider(BaseModel):
    id: str
    name: str
    available: bool = False
    models: Optional[list[str]] = []


# ── DORA Metrics ──

class DoraMetrics(BaseModel):
    deployment_frequency: Optional[float] = 0
    lead_time_hours: Optional[float] = 0
    change_failure_rate: Optional[float] = 0
    mttr_minutes: Optional[float] = 0
    period_days: Optional[int] = 30


# ── Ideation ──

class IdeationRequest(BaseModel):
    prompt: str = Field(min_length=3, example="e-commerce app in React")
    project_id: Optional[str] = ""


class IdeationResponse(BaseModel):
    session_id: str
    status: str = "started"


# ── Memory ──

class MemoryEntry(BaseModel):
    scope: Optional[str] = ""
    key: Optional[str] = ""
    content: str
    relevance: Optional[float] = 0


class MemoryStats(BaseModel):
    total_entries: int = 0
    by_scope: Optional[dict[str, int]] = {}


# ── AutoHeal ──

class AutoHealStats(BaseModel):
    total_heals: int = 0
    successful: int = 0
    failed: int = 0
    last_run: Optional[str] = None


# ── Backlog ──

class BacklogReorder(BaseModel):
    feature_ids: list[str]


class FeatureDep(BaseModel):
    feature_id: str
    depends_on: str


# ── Generic ──

class OkResponse(BaseModel):
    ok: bool = True
    id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str

