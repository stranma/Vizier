"""Tests for EA data models."""

from datetime import datetime, timedelta

from vizier.core.ea.models import (
    BriefingConfig,
    BudgetConfig,
    CheckinRecord,
    CheckoutRecord,
    Commitment,
    CommitmentStatus,
    FocusMode,
    PrioritiesConfig,
    Priority,
    PriorityLevel,
    Relationship,
)


class TestCommitment:
    def test_create_minimal(self) -> None:
        c = Commitment(id="c1", description="Deliver report", promised_to="Board")
        assert c.id == "c1"
        assert c.status == CommitmentStatus.PENDING
        assert c.deadline is None
        assert c.project is None

    def test_create_full(self) -> None:
        deadline = datetime(2026, 3, 15)
        c = Commitment(
            id="c2",
            description="API docs",
            promised_to="Novak",
            deadline=deadline,
            project="project-alpha",
            status=CommitmentStatus.IN_PROGRESS,
        )
        assert c.deadline == deadline
        assert c.project == "project-alpha"
        assert c.status == CommitmentStatus.IN_PROGRESS

    def test_serialization(self) -> None:
        c = Commitment(id="c1", description="Test", promised_to="Someone")
        data = c.model_dump(mode="json")
        assert data["id"] == "c1"
        c2 = Commitment(**data)
        assert c2.id == c.id


class TestRelationship:
    def test_create_minimal(self) -> None:
        r = Relationship(id="r1", name="Jan Novak")
        assert r.id == "r1"
        assert r.name == "Jan Novak"
        assert r.open_commitments == []

    def test_with_commitments(self) -> None:
        r = Relationship(
            id="r1",
            name="Jan Novak",
            role="Partner",
            open_commitments=["c1", "c2"],
            last_contact=datetime(2026, 2, 10),
        )
        assert len(r.open_commitments) == 2
        assert r.role == "Partner"


class TestPriorities:
    def test_empty_priorities(self) -> None:
        p = PrioritiesConfig()
        assert p.current_focus == ""
        assert p.priority_order == []
        assert p.standing_instructions == []

    def test_full_priorities(self) -> None:
        p = PrioritiesConfig(
            current_focus="Ship dashboard",
            priority_order=[
                Priority(project="alpha", reason="Board meeting", urgency=PriorityLevel.CRITICAL),
                Priority(project="beta", reason="Client deliverable", urgency=PriorityLevel.NORMAL),
            ],
            standing_instructions=["Always mention costs"],
        )
        assert len(p.priority_order) == 2
        assert p.priority_order[0].urgency == PriorityLevel.CRITICAL


class TestFocusMode:
    def test_inactive_is_expired(self) -> None:
        f = FocusMode()
        assert f.is_expired is True

    def test_active_not_expired(self) -> None:
        f = FocusMode(
            active=True,
            started_at=datetime.utcnow(),
            duration_hours=2.0,
        )
        assert f.is_expired is False

    def test_active_expired(self) -> None:
        f = FocusMode(
            active=True,
            started_at=datetime.utcnow() - timedelta(hours=3),
            duration_hours=2.0,
        )
        assert f.is_expired is True


class TestBudgetConfig:
    def test_defaults(self) -> None:
        b = BudgetConfig()
        assert b.monthly_budget_usd == 100.0
        assert b.alert_threshold == 0.8
        assert b.degrade_threshold == 1.0
        assert b.pause_threshold == 1.2

    def test_custom(self) -> None:
        b = BudgetConfig(monthly_budget_usd=500.0, alert_threshold=0.7)
        assert b.monthly_budget_usd == 500.0
        assert b.alert_threshold == 0.7


class TestBriefingConfig:
    def test_defaults(self) -> None:
        b = BriefingConfig()
        assert b.briefing_hour == 8
        assert b.include_cost_summary is True


class TestCheckoutRecord:
    def test_create(self) -> None:
        r = CheckoutRecord(file_path="docs/plan.xlsx", project="alpha")
        assert r.returned is False
        assert r.returned_at is None


class TestCheckinRecord:
    def test_create(self) -> None:
        r = CheckinRecord(
            id="ci-001",
            new_contacts=["Jan Novak"],
            decisions=["Use React"],
        )
        assert len(r.new_contacts) == 1
        assert len(r.decisions) == 1
