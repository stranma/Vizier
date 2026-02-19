"""Contract A: Typed message models for inter-agent communication (D54).

All inter-agent communication uses these Pydantic models. Messages are serialized
as JSON and written to the spec directory on the filesystem (source of truth).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PingUrgency(StrEnum):
    """Urgency levels for ping_supervisor (D50)."""

    INFO = "INFO"
    QUESTION = "QUESTION"
    BLOCKER = "BLOCKER"


class EscalationSeverity(StrEnum):
    """Severity levels for escalation messages."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(StrEnum):
    """Scout research recommendation types."""

    BUILD_FROM_SCRATCH = "BUILD_FROM_SCRATCH"
    USE_LIBRARY = "USE_LIBRARY"
    COMBINE = "COMBINE"


class CriterionResult(BaseModel):
    """Single criterion evaluation within a QUALITY_VERDICT."""

    criterion: str
    result: Literal["PASS", "FAIL"]
    evidence_link: str


class ResearchCandidate(BaseModel):
    """A candidate solution found during Scout research."""

    name: str
    source: str
    url: str
    description: str
    license: str = ""
    relevance: str = "medium"


class PlanStep(BaseModel):
    """A single step in an Architect's PROPOSE_PLAN."""

    sub_spec_id: str
    goal: str
    complexity: str = "medium"
    write_set: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class TaskAssignment(BaseModel):
    """EA -> Pasha, or Pasha -> any inner-loop agent."""

    type: Literal["TASK_ASSIGNMENT"] = "TASK_ASSIGNMENT"
    spec_id: str
    goal: str
    constraints: list[str] = Field(default_factory=list)
    budget_tokens: int = 100000
    allowed_tools: list[str] = Field(default_factory=list)
    assigned_role: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class StatusUpdate(BaseModel):
    """Any agent reports progress to its supervisor."""

    type: Literal["STATUS_UPDATE"] = "STATUS_UPDATE"
    spec_id: str
    state: str
    progress: str = ""
    blockers: list[str] = Field(default_factory=list)
    next_step: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tokens_used: int = 0
    timestamp: datetime = Field(default_factory=_utc_now)


class RequestClarification(BaseModel):
    """Any agent asks its supervisor for information."""

    type: Literal["REQUEST_CLARIFICATION"] = "REQUEST_CLARIFICATION"
    spec_id: str
    question: str
    options: list[str] = Field(default_factory=list)
    blocking: bool = False
    deadline: datetime | None = None
    context: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class ProposePlan(BaseModel):
    """Architect sends decomposition plan to Pasha for validation."""

    type: Literal["PROPOSE_PLAN"] = "PROPOSE_PLAN"
    spec_id: str
    steps: list[PlanStep]
    risks: list[str] = Field(default_factory=list)
    test_strategy: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class Escalation(BaseModel):
    """Any agent escalates a problem to its supervisor."""

    type: Literal["ESCALATION"] = "ESCALATION"
    spec_id: str
    severity: EscalationSeverity = EscalationSeverity.MEDIUM
    reason: str
    attempted: list[str] = Field(default_factory=list)
    needed_from_supervisor: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class QualityVerdict(BaseModel):
    """Quality Gate sends structured judgment with mandatory evidence (D56)."""

    type: Literal["QUALITY_VERDICT"] = "QUALITY_VERDICT"
    spec_id: str
    pass_fail: Literal["PASS", "FAIL"]
    criteria_results: list[CriterionResult] = Field(default_factory=list)
    suggested_fix: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


class ResearchReport(BaseModel):
    """Scout sends structured research findings."""

    type: Literal["RESEARCH_REPORT"] = "RESEARCH_REPORT"
    spec_id: str
    candidates: list[ResearchCandidate] = Field(default_factory=list)
    recommendation: Recommendation = Recommendation.BUILD_FROM_SCRATCH
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    search_queries: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


class Ping(BaseModel):
    """Immediate supervisor notification (D50)."""

    type: Literal["PING"] = "PING"
    spec_id: str
    urgency: PingUrgency = PingUrgency.INFO
    message: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


# Union type for message dispatch
AgentMessage = (
    TaskAssignment
    | StatusUpdate
    | RequestClarification
    | ProposePlan
    | Escalation
    | QualityVerdict
    | ResearchReport
    | Ping
)

# Type string -> model class mapping for deserialization
MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "TASK_ASSIGNMENT": TaskAssignment,
    "STATUS_UPDATE": StatusUpdate,
    "REQUEST_CLARIFICATION": RequestClarification,
    "PROPOSE_PLAN": ProposePlan,
    "ESCALATION": Escalation,
    "QUALITY_VERDICT": QualityVerdict,
    "RESEARCH_REPORT": ResearchReport,
    "PING": Ping,
}


def parse_message(data: dict[str, object]) -> AgentMessage:
    """Parse a raw dict into the correct message type based on 'type' field."""
    msg_type = data.get("type")
    if not isinstance(msg_type, str) or msg_type not in MESSAGE_TYPES:
        msg = f"Unknown or missing message type: {msg_type}"
        raise ValueError(msg)
    model_class = MESSAGE_TYPES[msg_type]
    return model_class.model_validate(data)  # type: ignore[return-value]
