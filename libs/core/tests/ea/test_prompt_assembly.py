"""Tests for JIT prompt assembly."""

from pathlib import Path

import yaml

from vizier.core.ea.classifier import ClassificationResult, MessageCategory, PromptModule
from vizier.core.ea.models import PrioritiesConfig, Priority, PriorityLevel
from vizier.core.ea.prompt_assembly import MODULE_PROMPTS, PromptAssembler


class TestPromptAssembler:
    def test_core_only(self) -> None:
        assembler = PromptAssembler(projects=["alpha", "beta"])
        classification = ClassificationResult(
            category=MessageCategory.GENERAL,
            modules=[PromptModule.CORE],
        )
        prompt = assembler.assemble(classification)
        assert "Vizier" in prompt
        assert "alpha" in prompt
        assert "beta" in prompt

    def test_with_priorities(self) -> None:
        assembler = PromptAssembler()
        classification = ClassificationResult(
            category=MessageCategory.GENERAL,
            modules=[PromptModule.CORE],
        )
        priorities = PrioritiesConfig(
            current_focus="Ship dashboard",
            priority_order=[
                Priority(project="alpha", reason="Board meeting", urgency=PriorityLevel.CRITICAL),
            ],
        )
        prompt = assembler.assemble(classification, priorities)
        assert "Ship dashboard" in prompt
        assert "alpha" in prompt
        assert "critical" in prompt

    def test_with_commitments(self) -> None:
        assembler = PromptAssembler()
        classification = ClassificationResult(
            category=MessageCategory.GENERAL,
            modules=[PromptModule.CORE],
        )
        prompt = assembler.assemble(
            classification,
            active_commitments=["Board deck due March 15", "API docs for Novak"],
        )
        assert "Board deck" in prompt
        assert "API docs" in prompt

    def test_jit_modules_loaded(self) -> None:
        assembler = PromptAssembler()
        classification = ClassificationResult(
            category=MessageCategory.CHECKIN,
            modules=[PromptModule.CORE, PromptModule.CHECKIN],
        )
        prompt = assembler.assemble(classification)
        assert "Check-in Protocol" in prompt

    def test_multiple_modules(self) -> None:
        assembler = PromptAssembler()
        classification = ClassificationResult(
            category=MessageCategory.CROSS_PROJECT,
            modules=[PromptModule.CORE, PromptModule.CROSS_PROJECT, PromptModule.CALENDAR],
        )
        prompt = assembler.assemble(classification)
        assert "Cross-Project" in prompt
        assert "Calendar" in prompt

    def test_no_projects(self) -> None:
        assembler = PromptAssembler()
        classification = ClassificationResult(
            category=MessageCategory.GENERAL,
            modules=[PromptModule.CORE],
        )
        prompt = assembler.assemble(classification)
        assert "No projects registered" in prompt

    def test_budget_module(self) -> None:
        assembler = PromptAssembler()
        classification = ClassificationResult(
            category=MessageCategory.BUDGET,
            modules=[PromptModule.CORE, PromptModule.BUDGET],
        )
        prompt = assembler.assemble(classification)
        assert "Budget" in prompt
        assert "80%" in prompt

    def test_standing_instructions(self) -> None:
        assembler = PromptAssembler()
        priorities = PrioritiesConfig(
            standing_instructions=["Always mention costs", "Escalate alpha blockers"],
        )
        classification = ClassificationResult(
            category=MessageCategory.GENERAL,
            modules=[PromptModule.CORE],
        )
        prompt = assembler.assemble(classification, priorities)
        assert "Always mention costs" in prompt
        assert "Standing instructions" in prompt


class TestLoadPriorities:
    def test_load_from_file(self, tmp_path: Path) -> None:
        priorities_data = {
            "current_focus": "Ship dashboard",
            "priority_order": [
                {"project": "alpha", "reason": "Board meeting", "urgency": "critical"},
            ],
            "standing_instructions": ["Always mention costs"],
        }
        priorities_path = tmp_path / "priorities.yaml"
        priorities_path.write_text(yaml.dump(priorities_data), encoding="utf-8")

        assembler = PromptAssembler(ea_data_dir=str(tmp_path))
        priorities = assembler.load_priorities()
        assert priorities.current_focus == "Ship dashboard"
        assert len(priorities.priority_order) == 1
        assert priorities.priority_order[0].urgency == PriorityLevel.CRITICAL

    def test_load_missing_file(self, tmp_path: Path) -> None:
        assembler = PromptAssembler(ea_data_dir=str(tmp_path))
        priorities = assembler.load_priorities()
        assert priorities.current_focus == ""
        assert priorities.priority_order == []

    def test_load_empty_file(self, tmp_path: Path) -> None:
        priorities_path = tmp_path / "priorities.yaml"
        priorities_path.write_text("", encoding="utf-8")
        assembler = PromptAssembler(ea_data_dir=str(tmp_path))
        priorities = assembler.load_priorities()
        assert priorities.current_focus == ""


class TestPromptSize:
    def test_core_prompt_under_target(self) -> None:
        assembler = PromptAssembler(projects=["alpha"])
        classification = ClassificationResult(
            category=MessageCategory.GENERAL,
            modules=[PromptModule.CORE],
        )
        prompt = assembler.assemble(classification)
        word_count = len(prompt.split())
        assert word_count < 800

    def test_all_modules_reasonable_size(self) -> None:
        for module, text in MODULE_PROMPTS.items():
            word_count = len(text.split())
            assert word_count < 300, f"Module {module} is {word_count} words, expected < 300"
