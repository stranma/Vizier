"""Tests for the deterministic message classifier."""

from vizier.core.ea.classifier import MessageCategory, MessageClassifier, PromptModule


class TestSlashCommands:
    def setup_method(self) -> None:
        self.classifier = MessageClassifier()

    def test_status_command(self) -> None:
        result = self.classifier.classify("/status")
        assert result.category == MessageCategory.STATUS

    def test_status_with_project(self) -> None:
        result = self.classifier.classify("/status project-alpha")
        assert result.category == MessageCategory.STATUS
        assert result.project == "project-alpha"

    def test_ask_command(self) -> None:
        result = self.classifier.classify("/ask project-alpha what framework?")
        assert result.category == MessageCategory.QUICK_QUERY
        assert result.project == "project-alpha"
        assert result.extra["query"] == "what framework?"

    def test_checkin_command(self) -> None:
        result = self.classifier.classify("/checkin")
        assert result.category == MessageCategory.CHECKIN
        assert PromptModule.CHECKIN in result.modules

    def test_focus_command(self) -> None:
        result = self.classifier.classify("/focus 3h")
        assert result.category == MessageCategory.FOCUS
        assert result.extra["duration_hours"] == "3"

    def test_session_command(self) -> None:
        result = self.classifier.classify("/session project-alpha")
        assert result.category == MessageCategory.SESSION
        assert result.project == "project-alpha"
        assert PromptModule.SESSION in result.modules

    def test_approve_command(self) -> None:
        result = self.classifier.classify("/approve spec-042")
        assert result.category == MessageCategory.APPROVAL
        assert result.extra["spec_id"] == "spec-042"

    def test_budget_command(self) -> None:
        result = self.classifier.classify("/budget")
        assert result.category == MessageCategory.BUDGET
        assert PromptModule.BUDGET in result.modules

    def test_budget_with_project(self) -> None:
        result = self.classifier.classify("/budget project-alpha")
        assert result.category == MessageCategory.BUDGET
        assert result.project == "project-alpha"

    def test_priorities_command(self) -> None:
        result = self.classifier.classify("/priorities")
        assert result.category == MessageCategory.PRIORITIES


class TestPatternClassification:
    def setup_method(self) -> None:
        self.classifier = MessageClassifier()

    def test_delegation_build(self) -> None:
        result = self.classifier.classify("Build auth for project-alpha")
        assert result.category == MessageCategory.DELEGATION
        assert result.project == "project-alpha"

    def test_delegation_create(self) -> None:
        result = self.classifier.classify("Create a dashboard for project-beta")
        assert result.category == MessageCategory.DELEGATION

    def test_delegation_fix(self) -> None:
        result = self.classifier.classify("Fix the login bug in project-alpha")
        assert result.category == MessageCategory.DELEGATION

    def test_status_hows_everything(self) -> None:
        result = self.classifier.classify("How's everything going?")
        assert result.category == MessageCategory.STATUS

    def test_status_progress(self) -> None:
        result = self.classifier.classify("What's the progress on project-alpha?")
        assert result.category == MessageCategory.STATUS

    def test_control_stop(self) -> None:
        result = self.classifier.classify("Stop work on project-beta")
        assert result.category == MessageCategory.CONTROL

    def test_control_cancel_task(self) -> None:
        result = self.classifier.classify("Cancel task on project-alpha")
        assert result.category == MessageCategory.CONTROL

    def test_file_ops(self) -> None:
        result = self.classifier.classify("Send me the document from project-alpha")
        assert result.category == MessageCategory.FILE_OPS
        assert PromptModule.FILE_OPS in result.modules

    def test_file_checkout(self) -> None:
        result = self.classifier.classify("I need to checkout the business plan")
        assert result.category == MessageCategory.FILE_OPS

    def test_direct_qa(self) -> None:
        result = self.classifier.classify("What framework does project-alpha use?")
        assert result.category == MessageCategory.DIRECT_QA

    def test_general_message(self) -> None:
        result = self.classifier.classify("Hello, good morning")
        assert result.category == MessageCategory.GENERAL

    def test_cross_project(self) -> None:
        result = self.classifier.classify("Status across all projects")
        assert result.category == MessageCategory.CROSS_PROJECT
        assert PromptModule.CROSS_PROJECT in result.modules

    def test_calendar_adds_module(self) -> None:
        result = self.classifier.classify("Build presentation for the meeting tomorrow")
        assert PromptModule.CALENDAR in result.modules


class TestModuleAssignment:
    def setup_method(self) -> None:
        self.classifier = MessageClassifier()

    def test_core_always_loaded(self) -> None:
        result = self.classifier.classify("Hello")
        assert PromptModule.CORE in result.modules

    def test_checkin_loads_checkin_module(self) -> None:
        result = self.classifier.classify("/checkin")
        assert PromptModule.CHECKIN in result.modules
        assert PromptModule.CORE in result.modules

    def test_budget_loads_budget_module(self) -> None:
        result = self.classifier.classify("/budget")
        assert PromptModule.BUDGET in result.modules

    def test_session_loads_session_module(self) -> None:
        result = self.classifier.classify("/session alpha")
        assert PromptModule.SESSION in result.modules


class TestProjectExtraction:
    def setup_method(self) -> None:
        self.classifier = MessageClassifier()

    def test_extracts_project_name(self) -> None:
        result = self.classifier.classify("Build auth for project-alpha")
        assert result.project == "project-alpha"

    def test_no_project(self) -> None:
        result = self.classifier.classify("Hello world")
        assert result.project == ""

    def test_project_prefix(self) -> None:
        result = self.classifier.classify("project-beta needs attention")
        assert result.project == "beta"
