"""Tests for process debt register."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.retrospective.debt_register import DebtEntry, DebtRegister


class TestDebtEntry:
    def test_to_dict(self) -> None:
        entry = DebtEntry(pattern="lint failures", severity="HIGH", frequency=3)
        d = entry.to_dict()
        assert d["pattern"] == "lint failures"
        assert d["severity"] == "HIGH"
        assert d["frequency"] == 3

    def test_from_dict(self) -> None:
        d = {"pattern": "test flakes", "severity": "MEDIUM", "frequency": 5, "evidence": ["001", "002"]}
        entry = DebtEntry.from_dict(d)
        assert entry.pattern == "test flakes"
        assert entry.frequency == 5
        assert len(entry.evidence) == 2

    def test_roundtrip(self) -> None:
        entry = DebtEntry(pattern="budget overrun", severity="HIGH", frequency=2, evidence=["001"])
        d = entry.to_dict()
        restored = DebtEntry.from_dict(d)
        assert restored.pattern == entry.pattern
        assert restored.severity == entry.severity
        assert restored.frequency == entry.frequency


class TestDebtRegister:
    def test_empty_register(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        assert reg.entries == []

    def test_add_entry(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        entry = reg.add("lint failures", "HIGH", "001")
        assert entry.pattern == "lint failures"
        assert entry.frequency == 1
        assert len(reg.entries) == 1

    def test_add_increments_frequency(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("lint failures", evidence="001")
        entry = reg.add("lint failures", evidence="002")
        assert entry.frequency == 2
        assert len(reg.entries) == 1
        assert len(entry.evidence) == 2

    def test_add_different_patterns(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("lint failures")
        reg.add("test flakes")
        assert len(reg.entries) == 2

    def test_resolve(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("lint failures")
        result = reg.resolve("lint failures", "Added pre-commit hook")
        assert result is True
        assert reg.entries[0].resolution == "Added pre-commit hook"

    def test_resolve_nonexistent(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        result = reg.resolve("nonexistent", "fix")
        assert result is False

    def test_unresolved(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("lint failures")
        reg.add("test flakes")
        reg.resolve("lint failures", "fixed")
        unresolved = reg.unresolved()
        assert len(unresolved) == 1
        assert unresolved[0].pattern == "test flakes"

    def test_high_severity(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("lint failures", "LOW")
        reg.add("data corruption", "HIGH")
        high = reg.high_severity()
        assert len(high) == 1
        assert high[0].pattern == "data corruption"

    def test_persistence(self, tmp_path: Path) -> None:
        path = str(tmp_path / "debt.json")
        reg1 = DebtRegister(path)
        reg1.add("lint failures", "HIGH", "001")
        reg1.add("test flakes", "MEDIUM", "002")

        reg2 = DebtRegister(path)
        assert len(reg2.entries) == 2
        assert reg2.entries[0].pattern == "lint failures"

    def test_format_register(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("lint failures", "HIGH")
        reg.add("lint failures")
        reg.add("test flakes", "LOW")
        text = reg.format_register()
        assert "lint failures" in text
        assert "freq: 2" in text
        assert "[HIGH]" in text

    def test_format_empty(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        assert "No process debt" in reg.format_register()

    def test_severity_escalation(self, tmp_path: Path) -> None:
        reg = DebtRegister(str(tmp_path / "debt.json"))
        reg.add("issue", "MEDIUM")
        entry = reg.add("issue", "HIGH")
        assert entry.severity == "HIGH"
