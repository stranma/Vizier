"""Tests for Contract A message models (D54)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vizier.core.models.messages import (
    CriterionResult,
    Escalation,
    EscalationSeverity,
    Ping,
    PingUrgency,
    PlanStep,
    ProposePlan,
    QualityVerdict,
    Recommendation,
    RequestClarification,
    ResearchCandidate,
    ResearchReport,
    StatusUpdate,
    TaskAssignment,
    parse_message,
)


class TestTaskAssignment:
    def test_minimal(self) -> None:
        msg = TaskAssignment(spec_id="001-auth", goal="Implement JWT auth")
        assert msg.type == "TASK_ASSIGNMENT"
        assert msg.spec_id == "001-auth"
        assert msg.goal == "Implement JWT auth"
        assert msg.constraints == []
        assert msg.budget_tokens == 100000
        assert msg.allowed_tools == []
        assert msg.assigned_role == ""
        assert msg.timestamp is not None

    def test_full(self) -> None:
        msg = TaskAssignment(
            spec_id="001-auth",
            goal="Implement JWT auth",
            constraints=["Use PyJWT", "No breaking changes"],
            budget_tokens=50000,
            allowed_tools=["read_file", "write_file", "bash"],
            assigned_role="worker",
        )
        assert msg.constraints == ["Use PyJWT", "No breaking changes"]
        assert msg.budget_tokens == 50000
        assert msg.allowed_tools == ["read_file", "write_file", "bash"]
        assert msg.assigned_role == "worker"

    def test_serialization_roundtrip(self) -> None:
        msg = TaskAssignment(spec_id="001", goal="Test")
        data = msg.model_dump(mode="json")
        restored = TaskAssignment.model_validate(data)
        assert restored.spec_id == msg.spec_id
        assert restored.type == "TASK_ASSIGNMENT"


class TestStatusUpdate:
    def test_minimal(self) -> None:
        msg = StatusUpdate(spec_id="001", state="IN_PROGRESS")
        assert msg.type == "STATUS_UPDATE"
        assert msg.confidence == 0.5
        assert msg.tokens_used == 0

    def test_confidence_bounds(self) -> None:
        msg = StatusUpdate(spec_id="001", state="IN_PROGRESS", confidence=0.0)
        assert msg.confidence == 0.0
        msg = StatusUpdate(spec_id="001", state="IN_PROGRESS", confidence=1.0)
        assert msg.confidence == 1.0

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            StatusUpdate(spec_id="001", state="IN_PROGRESS", confidence=1.5)
        with pytest.raises(ValidationError):
            StatusUpdate(spec_id="001", state="IN_PROGRESS", confidence=-0.1)


class TestRequestClarification:
    def test_blocking(self) -> None:
        msg = RequestClarification(
            spec_id="001",
            question="Which auth method?",
            options=["JWT", "OAuth"],
            blocking=True,
        )
        assert msg.type == "REQUEST_CLARIFICATION"
        assert msg.blocking is True
        assert msg.options == ["JWT", "OAuth"]
        assert msg.deadline is None

    def test_with_deadline(self) -> None:
        deadline = datetime(2026, 3, 1, tzinfo=UTC)
        msg = RequestClarification(spec_id="001", question="?", deadline=deadline)
        assert msg.deadline == deadline


class TestProposePlan:
    def test_with_steps_and_dag(self) -> None:
        steps = [
            PlanStep(sub_spec_id="001/001-model", goal="Data model", complexity="low"),
            PlanStep(
                sub_spec_id="001/002-api",
                goal="API endpoint",
                complexity="medium",
                depends_on=["001/001-model"],
                write_set=["src/api/**"],
            ),
        ]
        msg = ProposePlan(spec_id="001", steps=steps, risks=["Compatibility"])
        assert msg.type == "PROPOSE_PLAN"
        assert len(msg.steps) == 2
        assert msg.steps[1].depends_on == ["001/001-model"]
        assert msg.steps[1].write_set == ["src/api/**"]
        assert msg.risks == ["Compatibility"]

    def test_plan_step_defaults(self) -> None:
        step = PlanStep(sub_spec_id="001", goal="Test")
        assert step.complexity == "medium"
        assert step.write_set == []
        assert step.depends_on == []


class TestEscalation:
    def test_with_severity(self) -> None:
        msg = Escalation(
            spec_id="001",
            severity=EscalationSeverity.HIGH,
            reason="API changed",
            attempted=["Tried v2 API", "Checked migration guide"],
            needed_from_supervisor="Update spec",
        )
        assert msg.type == "ESCALATION"
        assert msg.severity == EscalationSeverity.HIGH
        assert len(msg.attempted) == 2

    def test_default_severity(self) -> None:
        msg = Escalation(spec_id="001", reason="Stuck")
        assert msg.severity == EscalationSeverity.MEDIUM


class TestQualityVerdict:
    def test_pass_verdict(self) -> None:
        criteria = [
            CriterionResult(criterion="Tests pass", result="PASS", evidence_link="evidence/test.txt"),
            CriterionResult(criterion="Lint clean", result="PASS", evidence_link="evidence/lint.txt"),
        ]
        msg = QualityVerdict(spec_id="001", pass_fail="PASS", criteria_results=criteria)
        assert msg.type == "QUALITY_VERDICT"
        assert msg.pass_fail == "PASS"
        assert len(msg.criteria_results) == 2
        assert msg.suggested_fix == []

    def test_fail_verdict(self) -> None:
        criteria = [CriterionResult(criterion="Tests pass", result="FAIL", evidence_link="evidence/test.txt")]
        msg = QualityVerdict(
            spec_id="001",
            pass_fail="FAIL",
            criteria_results=criteria,
            suggested_fix=["Fix failing test in test_auth.py"],
        )
        assert msg.pass_fail == "FAIL"
        assert len(msg.suggested_fix) == 1

    def test_invalid_pass_fail(self) -> None:
        with pytest.raises(ValidationError):
            QualityVerdict(spec_id="001", pass_fail="MAYBE")  # type: ignore[arg-type]


class TestResearchReport:
    def test_with_candidates(self) -> None:
        candidates = [
            ResearchCandidate(name="PyJWT", source="pypi", url="https://pypi.org/project/PyJWT/", description="JWT lib"),
        ]
        msg = ResearchReport(
            spec_id="001",
            candidates=candidates,
            recommendation=Recommendation.USE_LIBRARY,
            confidence=0.9,
            search_queries=["python jwt library"],
        )
        assert msg.type == "RESEARCH_REPORT"
        assert len(msg.candidates) == 1
        assert msg.recommendation == Recommendation.USE_LIBRARY
        assert msg.confidence == 0.9

    def test_skip_research(self) -> None:
        msg = ResearchReport(spec_id="001", confidence=0.85)
        assert msg.candidates == []
        assert msg.recommendation == Recommendation.BUILD_FROM_SCRATCH


class TestPing:
    def test_blocker(self) -> None:
        msg = Ping(spec_id="001", urgency=PingUrgency.BLOCKER, message="Cannot proceed")
        assert msg.type == "PING"
        assert msg.urgency == PingUrgency.BLOCKER
        assert msg.message == "Cannot proceed"

    def test_default_info(self) -> None:
        msg = Ping(spec_id="001")
        assert msg.urgency == PingUrgency.INFO

    def test_all_urgency_levels(self) -> None:
        for level in PingUrgency:
            msg = Ping(spec_id="001", urgency=level)
            assert msg.urgency == level


class TestParseMessage:
    def test_parse_task_assignment(self) -> None:
        data = {"type": "TASK_ASSIGNMENT", "spec_id": "001", "goal": "Test"}
        msg = parse_message(data)
        assert isinstance(msg, TaskAssignment)
        assert msg.spec_id == "001"

    def test_parse_status_update(self) -> None:
        data = {"type": "STATUS_UPDATE", "spec_id": "001", "state": "REVIEW"}
        msg = parse_message(data)
        assert isinstance(msg, StatusUpdate)

    def test_parse_ping(self) -> None:
        data = {"type": "PING", "spec_id": "001", "urgency": "BLOCKER", "message": "help"}
        msg = parse_message(data)
        assert isinstance(msg, Ping)
        assert msg.urgency == PingUrgency.BLOCKER

    def test_parse_quality_verdict(self) -> None:
        data = {
            "type": "QUALITY_VERDICT",
            "spec_id": "001",
            "pass_fail": "PASS",
            "criteria_results": [{"criterion": "Tests", "result": "PASS", "evidence_link": "e/t.txt"}],
        }
        msg = parse_message(data)
        assert isinstance(msg, QualityVerdict)
        assert len(msg.criteria_results) == 1

    def test_parse_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown or missing message type"):
            parse_message({"type": "UNKNOWN", "spec_id": "001"})

    def test_parse_missing_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown or missing message type"):
            parse_message({"spec_id": "001"})

    def test_all_message_types_parseable(self) -> None:
        """Every message type can be round-tripped through parse_message."""
        messages = [
            TaskAssignment(spec_id="001", goal="Test"),
            StatusUpdate(spec_id="001", state="REVIEW"),
            RequestClarification(spec_id="001", question="?"),
            ProposePlan(spec_id="001", steps=[PlanStep(sub_spec_id="001/001", goal="Step 1")]),
            Escalation(spec_id="001", reason="Stuck"),
            QualityVerdict(spec_id="001", pass_fail="PASS"),
            ResearchReport(spec_id="001"),
            Ping(spec_id="001"),
        ]
        for msg in messages:
            data = msg.model_dump(mode="json")
            restored = parse_message(data)
            assert type(restored) is type(msg)
            assert restored.spec_id == msg.spec_id


class TestJsonSchemaGeneration:
    def test_all_models_have_json_schema(self) -> None:
        """All message models generate valid JSON Schema for Anthropic tool definitions."""
        models = [
            TaskAssignment,
            StatusUpdate,
            RequestClarification,
            ProposePlan,
            Escalation,
            QualityVerdict,
            ResearchReport,
            Ping,
        ]
        for model in models:
            schema = model.model_json_schema()
            assert "properties" in schema
            assert "type" in schema["properties"]
