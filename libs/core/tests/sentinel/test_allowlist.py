"""Tests for allowlist policy."""

from vizier.core.sentinel.allowlist import AllowlistPolicy
from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest


class TestAllowlistPolicy:
    def setup_method(self) -> None:
        self.policy = AllowlistPolicy()

    def test_safe_tools_allowed(self) -> None:
        for tool in ("read_file", "file_read", "glob", "grep", "ls"):
            req = ToolCallRequest(tool=tool)
            result = self.policy.evaluate(req)
            assert result.decision == PolicyDecision.ALLOW, f"{tool} should be allowed"

    def test_file_write_allowed(self) -> None:
        for tool in ("file_write", "write_file", "file_edit"):
            req = ToolCallRequest(tool=tool)
            result = self.policy.evaluate(req)
            assert result.decision == PolicyDecision.ALLOW

    def test_safe_git_commands(self) -> None:
        safe_commands = ["git status", "git log --oneline", "git diff HEAD", "git branch -a", "git commit -m 'test'"]
        for cmd in safe_commands:
            req = ToolCallRequest(tool="bash", command=cmd)
            result = self.policy.evaluate(req)
            assert result.decision == PolicyDecision.ALLOW, f"'{cmd}' should be allowed"

    def test_safe_test_commands(self) -> None:
        for cmd in ["pytest tests/", "uv run pytest -v", "uv run ruff check .", "uv run ruff format --check ."]:
            req = ToolCallRequest(tool="bash", command=cmd)
            result = self.policy.evaluate(req)
            assert result.decision == PolicyDecision.ALLOW, f"'{cmd}' should be allowed"

    def test_unknown_tool_abstains(self) -> None:
        req = ToolCallRequest(tool="custom_tool")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ABSTAIN

    def test_unknown_bash_command_abstains(self) -> None:
        req = ToolCallRequest(tool="bash", command="some_random_command --flag")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ABSTAIN

    def test_git_push_without_force_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git push origin main")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_pyright_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="uv run pyright")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW
