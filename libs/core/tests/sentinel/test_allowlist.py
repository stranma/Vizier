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

    def test_git_blame_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git blame src/main.py")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_reflog_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git reflog show HEAD")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_describe_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git describe --tags")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_shortlog_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git shortlog -sn")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_rev_list_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git rev-list --count HEAD")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_stash_push_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git stash push -m 'wip'")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_stash_pop_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git stash pop")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_stash_list_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git stash list")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_fetch_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git fetch origin")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_pull_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git pull origin main")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_add_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git add .")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_remote_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git remote -v")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_tag_allowed(self) -> None:
        req = ToolCallRequest(tool="bash", command="git tag v1.0.0")
        result = self.policy.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

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
