"""
Macaron Agent Platform - Data Models
=====================================
Pydantic models for agents, messages, sessions, artifacts.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    BLOCKED = "blocked"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    DELEGATE = "delegate"
    VETO = "veto"
    APPROVE = "approve"
    INFORM = "inform"
    NEGOTIATE = "negotiate"
    ESCALATE = "escalate"
    HUMAN_REQUEST = "human_request"
    HUMAN_RESPONSE = "human_response"
    SYSTEM = "system"


class SessionStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationPattern(str, Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    LOOP = "loop"
    ROUTER = "router"
    AGGREGATOR = "aggregator"
    HIERARCHICAL = "hierarchical"
    NETWORK = "network"
    HUMAN_IN_LOOP = "human_in_loop"


class ArtifactType(str, Enum):
    CODE = "code"
    SPEC = "spec"
    TEST = "test"
    DOC = "doc"
    CONFIG = "config"
    DIAGRAM = "diagram"
    REVIEW = "review"
    REPORT = "report"


class VetoLevel(str, Enum):
    ABSOLUTE = "absolute"       # Cannot be overridden (security)
    STRONG = "strong"           # Requires escalation to override
    ADVISORY = "advisory"       # Can be overridden with justification


# ============================================================================
# AGENT MODELS
# ============================================================================

class AgentPermissions(BaseModel):
    """What an agent is allowed to do."""
    can_veto: bool = False
    veto_level: VetoLevel = VetoLevel.ADVISORY
    can_delegate: bool = False
    can_approve: bool = False
    escalation_to: Optional[str] = None
    require_human_approval_for: list[str] = Field(default_factory=list)


class AgentCommunication(BaseModel):
    """Who the agent can talk to."""
    responds_to: list[str] = Field(default_factory=list)
    can_contact: list[str] = Field(default_factory=list)
    broadcast_channels: list[str] = Field(default_factory=list)


class AgentTrigger(BaseModel):
    """Automatic trigger for an agent."""
    event: str                   # "on_code_pushed", "on_test_failed", etc.
    action: str                  # What to do
    auto: bool = False           # Auto-execute or wait for approval


class AgentLLMConfig(BaseModel):
    """LLM configuration for an agent."""
    model: str = "gpt-5.1"
    temperature: float = 0.7
    max_tokens: int = 4096
    fallback_model: Optional[str] = None


class AgentRole(BaseModel):
    """Definition of an agent role (loaded from YAML)."""
    id: str
    name: str
    role: str = ""
    avatar: str = ""
    tagline: str = ""
    version: str = "1.0"
    description: str = ""
    system_prompt: str = ""
    persona_traits: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    llm: AgentLLMConfig = Field(default_factory=AgentLLMConfig)
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    communication: AgentCommunication = Field(default_factory=AgentCommunication)
    triggers: list[AgentTrigger] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class AgentInstance(BaseModel):
    """A running instance of an agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role_id: str
    session_id: Optional[str] = None
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    memory_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    messages_sent: int = 0
    messages_received: int = 0
    tokens_used: int = 0
    error_count: int = 0


# ============================================================================
# A2A MESSAGE MODELS
# ============================================================================

class A2AMessage(BaseModel):
    """A message between agents (Agent-to-Agent protocol)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    from_agent: str                          # Agent instance ID or "user"
    to_agent: Optional[str] = None           # None = broadcast
    message_type: MessageType = MessageType.INFORM
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    parent_id: Optional[str] = None          # Thread chain
    priority: int = 5                        # 1=low, 10=critical
    requires_response: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NegotiationState(BaseModel):
    """State of an ongoing negotiation between agents."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    topic: str
    initiator: str
    participants: list[str]
    proposals: list[A2AMessage] = Field(default_factory=list)
    votes: dict[str, str] = Field(default_factory=dict)  # agent_id → "accept"|"reject"|"counter"
    status: str = "open"  # open, accepted, rejected, escalated
    round: int = 0
    max_rounds: int = 10
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# SESSION MODELS
# ============================================================================

class Session(BaseModel):
    """A collaborative work session."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    pattern: OrchestrationPattern = OrchestrationPattern.HIERARCHICAL
    agents: list[str] = Field(default_factory=list)       # Agent instance IDs
    status: SessionStatus = SessionStatus.PLANNING
    goal: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None                      # Link to Factory project
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ============================================================================
# ARTIFACT MODELS
# ============================================================================

class Artifact(BaseModel):
    """A shared artifact produced by agents."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    type: ArtifactType = ArtifactType.CODE
    name: str
    content: str = ""
    language: Optional[str] = None          # For code: "python", "rust", etc.
    version: int = 1
    created_by: str                         # Agent instance ID
    last_modified_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# TOOL MODELS
# ============================================================================

class ToolDefinition(BaseModel):
    """Definition of a tool available to agents."""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)  # JSON Schema
    requires_approval: bool = False
    allowed_roles: list[str] = Field(default_factory=list)     # Empty = all
    category: str = "general"                                   # code, git, build, azure


class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool_name: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0
    agent_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# METRICS
# ============================================================================

class AgentMetrics(BaseModel):
    """Aggregated metrics for an agent."""
    agent_id: str
    role_id: str
    total_messages: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_vetos: int = 0
    total_approvals: int = 0
    avg_response_time_ms: float = 0
    success_rate: float = 0
    period_start: datetime = Field(default_factory=datetime.utcnow)
    period_end: Optional[datetime] = None
