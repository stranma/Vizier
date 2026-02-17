"""Tests for EA runtime."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import yaml

from vizier.core.ea.models import (
    CheckinRecord,
    CheckoutRecord,
    Commitment,
)
from vizier.core.ea.runtime import EARuntime


def _make_ea(tmp_path: Path, **kwargs) -> EARuntime:  # type: ignore[no-untyped-def]
    """Create an EARuntime with test defaults."""
    ea_dir = tmp_path / "ea"
    reports_dir = tmp_path / "reports"
    projects = kwargs.pop("projects", {"alpha": str(tmp_path / "projects" / "alpha")})
    return EARuntime(
        ea_data_dir=str(ea_dir),
        reports_dir=str(reports_dir),
        projects=projects,
        **kwargs,
    )


class TestStatusHandling:
    def test_no_status_data(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/status")
        assert "No project status" in result

    def test_reads_status_json(self, tmp_path: Path) -> None:
        reports_dir = tmp_path / "reports" / "alpha"
        reports_dir.mkdir(parents=True)
        status = {"project": "alpha", "total_specs": 10, "done_count": 7, "stuck_count": 1}
        (reports_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")

        ea = _make_ea(tmp_path)
        result = ea.handle_message("/status")
        assert "alpha" in result
        assert "10" in result

    def test_status_specific_project(self, tmp_path: Path) -> None:
        reports_dir = tmp_path / "reports" / "alpha"
        reports_dir.mkdir(parents=True)
        status = {"project": "alpha", "total_specs": 5}
        (reports_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")

        ea = _make_ea(tmp_path)
        result = ea.handle_message("/status alpha")
        assert "alpha" in result

    def test_status_unknown_project(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/status nonexistent")
        assert "No status" in result


class TestDelegation:
    def test_delegates_to_project(self, tmp_path: Path) -> None:
        project_root = tmp_path / "projects" / "alpha"
        project_root.mkdir(parents=True)
        specs_dir = project_root / ".vizier" / "specs"
        specs_dir.mkdir(parents=True)

        ea = _make_ea(tmp_path, projects={"alpha": str(project_root)})
        result = ea.handle_message("Build auth for alpha")
        assert "delegated" in result.lower()
        assert "alpha" in result

    def test_delegation_single_project_default(self, tmp_path: Path) -> None:
        project_root = tmp_path / "projects" / "only"
        project_root.mkdir(parents=True)
        specs_dir = project_root / ".vizier" / "specs"
        specs_dir.mkdir(parents=True)

        ea = _make_ea(tmp_path, projects={"only": str(project_root)})
        result = ea.handle_message("Build a dashboard")
        assert "delegated" in result.lower()

    def test_delegation_unknown_project(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path, projects={"alpha": str(tmp_path / "alpha")})
        result = ea.handle_message("Build auth for project-nonexistent")
        assert "Unknown project" in result or "nonexistent" in result

    def test_delegation_multiple_projects_no_target(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path, projects={"alpha": "/a", "beta": "/b"})
        result = ea.handle_message("Build a new feature")
        assert "Which project" in result


class TestBudget:
    def test_budget_no_data(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/budget")
        assert "$0.00" in result

    def test_budget_with_entries(self, tmp_path: Path) -> None:
        reports_dir = tmp_path / "reports" / "alpha"
        reports_dir.mkdir(parents=True)
        entries = [
            {"agent": "worker", "cost_usd": 0.50},
            {"agent": "quality_gate", "cost_usd": 0.30},
        ]
        (reports_dir / "agent-log.jsonl").write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

        ea = _make_ea(tmp_path)
        result = ea.handle_message("/budget")
        assert "$0.80" in result

    def test_budget_specific_project(self, tmp_path: Path) -> None:
        reports_dir = tmp_path / "reports" / "alpha"
        reports_dir.mkdir(parents=True)
        (reports_dir / "agent-log.jsonl").write_text(json.dumps({"cost_usd": 10.0}), encoding="utf-8")

        ea = _make_ea(tmp_path)
        result = ea.handle_message("/budget alpha")
        assert "$10.00" in result
        assert "alpha" in result


class TestPriorities:
    def test_no_priorities(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/priorities")
        assert "No priorities" in result

    def test_reads_priorities(self, tmp_path: Path) -> None:
        ea_dir = tmp_path / "ea"
        ea_dir.mkdir(parents=True)
        priorities = {
            "current_focus": "Ship dashboard",
            "priority_order": [{"project": "alpha", "reason": "Board meeting", "urgency": "critical"}],
        }
        (ea_dir / "priorities.yaml").write_text(yaml.dump(priorities), encoding="utf-8")

        ea = _make_ea(tmp_path)
        result = ea.handle_message("/priorities")
        assert "Ship dashboard" in result
        assert "alpha" in result


class TestFocusMode:
    def test_activate_focus(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/focus 3h")
        assert "Focus mode activated" in result
        assert "3" in result

    def test_messages_held_during_focus(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        ea.handle_message("/focus 2h")
        result = ea.handle_message("How's everything?")
        assert "held" in result.lower()

    def test_control_bypasses_focus(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path, projects={"alpha": str(tmp_path / "alpha")})
        ea.handle_message("/focus 2h")
        result = ea.handle_message("Stop work on project-alpha")
        assert "Control command" in result

    def test_release_focus(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        ea.handle_message("/focus 2h")
        ea.handle_message("Message 1")
        ea.handle_message("Message 2")
        held = ea.release_focus()
        assert len(held) == 2
        assert ea.focus_mode.active is False


class TestQuickQuery:
    def test_quick_query(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/ask alpha what framework?")
        assert "Routing query" in result
        assert "alpha" in result

    def test_quick_query_no_project(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/ask")
        assert "specify" in result.lower()

    def test_quick_query_unknown_project(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("/ask unknown what?")
        assert "Unknown project" in result


class TestEscalations:
    def test_no_escalations(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        assert ea.get_escalations() == []

    def test_reads_escalation_files(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "reports" / "alpha" / "escalations"
        esc_dir.mkdir(parents=True)
        (esc_dir / "2026-02-16-spec-001.md").write_text("Spec stuck after 10 retries", encoding="utf-8")

        ea = _make_ea(tmp_path)
        escalations = ea.get_escalations()
        assert len(escalations) == 1
        assert escalations[0]["project"] == "alpha"


class TestBriefing:
    def test_generate_briefing_minimal(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        briefing = ea.generate_briefing()
        assert "Morning Briefing" in briefing
        assert "$" in briefing

    def test_briefing_with_overdue_commitments(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        past = datetime.utcnow() - timedelta(days=5)
        ea.commitments.create(Commitment(id="c1", description="Board deck", promised_to="Board", deadline=past))
        briefing = ea.generate_briefing()
        assert "Overdue" in briefing
        assert "Board deck" in briefing

    def test_briefing_with_escalations(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "reports" / "alpha" / "escalations"
        esc_dir.mkdir(parents=True)
        (esc_dir / "alert.md").write_text("Worker stuck", encoding="utf-8")

        ea = _make_ea(tmp_path)
        briefing = ea.generate_briefing()
        assert "Escalation" in briefing


class TestGeneral:
    def test_general_no_llm(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        result = ea.handle_message("Hello, good morning")
        assert "LLM not configured" in result

    def test_general_with_llm(self, tmp_path: Path) -> None:
        llm = MagicMock()
        llm.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Good morning, Sultan!"))]
        )
        ea = _make_ea(tmp_path, llm_callable=llm)
        result = ea.handle_message("Hello, good morning")
        assert "Good morning" in result
        llm.assert_called_once()

    def test_general_llm_error(self, tmp_path: Path) -> None:
        llm = MagicMock(side_effect=RuntimeError("API error"))
        ea = _make_ea(tmp_path, llm_callable=llm)
        result = ea.handle_message("Hello")
        assert "error" in result.lower()


class TestConversationHistory:
    def test_history_included_in_llm_call(self, tmp_path: Path) -> None:
        """Verify LLM receives prior turns in messages array."""
        llm = MagicMock()
        llm.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Response"))])
        ea = _make_ea(tmp_path, llm_callable=llm)

        ea.handle_message("Hello, good morning")
        ea.handle_message("What did I just say?")

        call_args = llm.call_args_list[1]
        messages = call_args.kwargs.get("messages") or call_args[1]["messages"]
        # system + history (user turn 1 + assistant turn 1) + current user = 4 minimum
        assert len(messages) >= 4
        roles = [m["role"] for m in messages]
        assert roles[0] == "system"
        assert roles[-1] == "user"
        assert "Hello, good morning" in messages[1]["content"]

    def test_history_survives_restart(self, tmp_path: Path) -> None:
        """Verify conversation persists across EARuntime instances."""
        llm = MagicMock()
        llm.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Noted about Friday"))]
        )
        ea1 = _make_ea(tmp_path, llm_callable=llm)
        ea1.handle_message("Remember: project deadline is Friday")

        ea2 = _make_ea(tmp_path, llm_callable=llm)
        ea2.handle_message("What is the deadline?")

        call_args = llm.call_args_list[-1]
        messages = call_args.kwargs.get("messages") or call_args[1]["messages"]
        history_content = " ".join(m["content"] for m in messages if m["role"] != "system")
        assert "Friday" in history_content

    def test_deterministic_handlers_skip_llm_history(self, tmp_path: Path) -> None:
        """Status, budget etc. don't use LLM, so history doesn't affect them."""
        ea = _make_ea(tmp_path)
        ea.handle_message("Hello")
        result = ea.handle_message("/status")
        assert "No project status" in result

    def test_reply_context_forwarded(self, tmp_path: Path) -> None:
        """Verify [Replying to: ...] prefix reaches LLM."""
        llm = MagicMock()
        llm.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Got it"))])
        ea = _make_ea(tmp_path, llm_callable=llm)
        ea.handle_message("[Replying to: Task delegated to alpha.]\n\nYou sent me this")

        call_args = llm.call_args
        messages = call_args.kwargs.get("messages") or call_args[1]["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("Replying to" in m["content"] for m in user_msgs)

    def test_conversation_logged_for_all_categories(self, tmp_path: Path) -> None:
        """All message categories are logged, not just general."""
        ea = _make_ea(tmp_path)
        ea.handle_message("/status")
        ea.handle_message("/budget")

        log_path = tmp_path / "ea" / "sessions" / "conversation.jsonl"
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 4


class TestCheckin:
    def test_record_checkin(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        record = CheckinRecord(
            id="ci-001",
            new_contacts=["Jan Novak"],
            decisions=["Use React"],
        )
        path = ea.record_checkin(record)
        assert path.exists()
        assert "ci-001" in str(path)

    def test_checkin_no_tmp_files(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        ea.record_checkin(CheckinRecord(id="ci-001"))
        checkins_dir = tmp_path / "ea" / "checkins"
        tmp_files = list(checkins_dir.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestCheckout:
    def test_track_checkout(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        checkout = CheckoutRecord(file_path="docs/plan.xlsx", project="alpha")
        path = ea.track_checkout(checkout)
        assert path.exists()

    def test_multiple_checkouts(self, tmp_path: Path) -> None:
        ea = _make_ea(tmp_path)
        ea.track_checkout(CheckoutRecord(file_path="file1.txt", project="alpha"))
        ea.track_checkout(CheckoutRecord(file_path="file2.txt", project="alpha"))
        checkouts_path = tmp_path / "ea" / "checkouts.yaml"
        data = yaml.safe_load(checkouts_path.read_text(encoding="utf-8"))
        assert len(data) == 2
