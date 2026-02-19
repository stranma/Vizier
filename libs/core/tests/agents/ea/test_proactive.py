"""Tests for EA proactive behaviors."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from vizier.core.agents.ea.proactive import (
    TriggerType,
    check_completion_notices,
    check_deadline_warnings,
    check_escalation_alerts,
    check_morning_briefing,
    collect_triggers,
)


class TestMorningBriefing:
    def test_triggers_at_8am(self) -> None:
        trigger = check_morning_briefing(hour=8)
        assert trigger is not None
        assert trigger.trigger_type == TriggerType.MORNING_BRIEFING
        assert trigger.priority == 1
        assert "morning briefing" in trigger.message.lower()

    def test_no_trigger_at_other_hours(self) -> None:
        for hour in [0, 7, 9, 12, 23]:
            assert check_morning_briefing(hour=hour) is None


class TestEscalationAlerts:
    def test_no_reports_dir(self) -> None:
        triggers = check_escalation_alerts("/nonexistent/path")
        assert triggers == []

    def test_finds_escalation_files(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "project-alpha" / "escalations"
        esc_dir.mkdir(parents=True)
        data = {"severity": "high", "reason": "Tests keep failing"}
        (esc_dir / "esc-001.json").write_text(json.dumps(data))
        triggers = check_escalation_alerts(str(tmp_path))
        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.ESCALATION_ALERT
        assert triggers[0].priority == 1
        assert "Tests keep failing" in triggers[0].message

    def test_medium_severity_lower_priority(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "project-beta" / "escalations"
        esc_dir.mkdir(parents=True)
        data = {"severity": "medium", "reason": "Minor issue"}
        (esc_dir / "esc-002.json").write_text(json.dumps(data))
        triggers = check_escalation_alerts(str(tmp_path))
        assert len(triggers) == 1
        assert triggers[0].priority == 2

    def test_skips_non_json(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "project" / "escalations"
        esc_dir.mkdir(parents=True)
        (esc_dir / "notes.txt").write_text("not json")
        triggers = check_escalation_alerts(str(tmp_path))
        assert triggers == []

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "project" / "escalations"
        esc_dir.mkdir(parents=True)
        (esc_dir / "bad.json").write_text("{invalid")
        triggers = check_escalation_alerts(str(tmp_path))
        assert triggers == []


class TestCompletionNotices:
    def test_no_specs_dir(self) -> None:
        triggers = check_completion_notices("/nonexistent")
        assert triggers == []

    def test_finds_done_specs(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001-auth"
        spec_dir.mkdir(parents=True)
        state = {"status": "DONE"}
        (spec_dir / "state.json").write_text(json.dumps(state))
        triggers = check_completion_notices(str(tmp_path))
        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.COMPLETION_NOTICE
        assert "001-auth" in triggers[0].message

    def test_skips_in_progress(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001-auth"
        spec_dir.mkdir(parents=True)
        state = {"status": "IN_PROGRESS"}
        (spec_dir / "state.json").write_text(json.dumps(state))
        triggers = check_completion_notices(str(tmp_path))
        assert triggers == []

    def test_skips_already_notified(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001-auth"
        spec_dir.mkdir(parents=True)
        state = {"status": "DONE", "notified": True}
        (spec_dir / "state.json").write_text(json.dumps(state))
        triggers = check_completion_notices(str(tmp_path))
        assert triggers == []


class TestDeadlineWarnings:
    def test_no_commitments_dir(self) -> None:
        triggers = check_deadline_warnings("/nonexistent")
        assert triggers == []

    def test_finds_approaching_deadline(self, tmp_path: Path) -> None:
        from datetime import UTC, datetime, timedelta

        deadline = datetime.now(UTC) + timedelta(days=1)
        content = f"name: board-deck\ndeadline: {deadline.isoformat()}\nstatus: in_progress\n"
        (tmp_path / "board-deck.yaml").write_text(content)
        triggers = check_deadline_warnings(str(tmp_path), warning_days=2)
        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.DEADLINE_WARNING
        assert "board-deck" in triggers[0].message

    def test_ignores_distant_deadline(self, tmp_path: Path) -> None:
        from datetime import UTC, datetime, timedelta

        deadline = datetime.now(UTC) + timedelta(days=30)
        content = f"name: future-task\ndeadline: {deadline.isoformat()}\nstatus: planned\n"
        (tmp_path / "future-task.yaml").write_text(content)
        triggers = check_deadline_warnings(str(tmp_path), warning_days=2)
        assert triggers == []

    def test_today_deadline_highest_priority(self, tmp_path: Path) -> None:
        from datetime import UTC, datetime, timedelta

        deadline = datetime.now(UTC) + timedelta(hours=6)
        content = f"name: urgent\ndeadline: {deadline.isoformat()}\nstatus: active\n"
        (tmp_path / "urgent.yaml").write_text(content)
        triggers = check_deadline_warnings(str(tmp_path), warning_days=2)
        assert len(triggers) == 1
        assert triggers[0].priority == 1


class TestCollectTriggers:
    def test_empty_when_no_dirs(self) -> None:
        triggers = collect_triggers(hour=10)
        assert triggers == []

    def test_morning_briefing_included(self) -> None:
        triggers = collect_triggers(hour=8)
        assert len(triggers) == 1
        assert triggers[0].trigger_type == TriggerType.MORNING_BRIEFING

    def test_sorted_by_priority(self, tmp_path: Path) -> None:
        esc_dir = tmp_path / "reports" / "project" / "escalations"
        esc_dir.mkdir(parents=True)
        (esc_dir / "esc.json").write_text(json.dumps({"severity": "medium", "reason": "Minor"}))
        triggers = collect_triggers(reports_dir=str(tmp_path / "reports"), hour=8)
        assert len(triggers) == 2
        assert triggers[0].priority <= triggers[1].priority

    def test_combines_all_sources(self, tmp_path: Path) -> None:
        reports = tmp_path / "reports"
        project = tmp_path / "project"
        commitments = tmp_path / "commitments"

        esc_dir = reports / "proj-a" / "escalations"
        esc_dir.mkdir(parents=True)
        (esc_dir / "e.json").write_text(json.dumps({"severity": "low", "reason": "FYI"}))

        spec_dir = project / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "DONE"}))

        triggers = collect_triggers(
            reports_dir=str(reports),
            project_root=str(project),
            commitments_dir=str(commitments),
            hour=10,
        )
        assert len(triggers) >= 2
