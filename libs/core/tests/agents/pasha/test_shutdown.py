"""Tests for graceful shutdown and recovery."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from vizier.core.agents.pasha.shutdown import graceful_shutdown, recover_interrupted


class TestGracefulShutdown:
    def test_interrupts_in_progress(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "IN_PROGRESS"}))
        interrupted = graceful_shutdown(str(tmp_path))
        assert interrupted == ["001"]
        with open(spec_dir / "state.json") as f:
            state = json.load(f)
        assert state["status"] == "INTERRUPTED"
        assert "interrupted_at" in state

    def test_skips_non_in_progress(self, tmp_path: Path) -> None:
        for sid, status in [("001", "DONE"), ("002", "READY"), ("003", "REVIEW")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))
        interrupted = graceful_shutdown(str(tmp_path))
        assert interrupted == []

    def test_multiple_in_progress(self, tmp_path: Path) -> None:
        for sid in ["001", "002", "003"]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": "IN_PROGRESS"}))
        interrupted = graceful_shutdown(str(tmp_path))
        assert len(interrupted) == 3

    def test_empty_project(self, tmp_path: Path) -> None:
        interrupted = graceful_shutdown(str(tmp_path))
        assert interrupted == []

    def test_handles_invalid_state(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text("{invalid")
        interrupted = graceful_shutdown(str(tmp_path))
        assert interrupted == []


class TestRecoverInterrupted:
    def test_finds_interrupted(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "INTERRUPTED"}))
        recovered = recover_interrupted(str(tmp_path))
        assert recovered == ["001"]

    def test_skips_non_interrupted(self, tmp_path: Path) -> None:
        for sid, status in [("001", "DONE"), ("002", "IN_PROGRESS")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))
        recovered = recover_interrupted(str(tmp_path))
        assert recovered == []

    def test_empty_project(self, tmp_path: Path) -> None:
        recovered = recover_interrupted(str(tmp_path))
        assert recovered == []
