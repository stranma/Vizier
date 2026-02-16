"""Tests for git operation classifier."""

from vizier.core.sentinel.git_classifier import GitOperationClassifier, GitSafety
from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest


class TestGitOperationClassifier:
    def setup_method(self) -> None:
        self.classifier = GitOperationClassifier()

    def test_safe_operations(self) -> None:
        safe_commands = [
            "git status",
            "git log --oneline",
            "git diff HEAD",
            "git commit -m 'test'",
            "git push origin main",
            "git pull origin main",
            "git fetch origin",
            "git checkout -b feature/test",
            "git add .",
            "git branch -a",
            "git clone https://github.com/test/repo",
            "git blame src/main.py",
            "git reflog show HEAD",
            "git describe --tags",
            "git shortlog -sn",
            "git rev-list --count HEAD",
            "git stash push -m 'wip'",
            "git stash pop",
            "git stash list",
            "git stash apply",
        ]
        for cmd in safe_commands:
            assert self.classifier.classify(cmd) == GitSafety.SAFE, f"'{cmd}' should be safe"

    def test_dangerous_operations(self) -> None:
        dangerous_commands = [
            "git push --force origin main",
            "git push -f origin main",
            "git reset --hard HEAD~3",
            "git rebase -i HEAD~5",
            "git clean -fd",
            "git clean -n",
            "git branch -D feature/old",
            "git checkout .",
            "git restore .",
            "git restore src/main.py",
            "git restore --staged file.py",
            "git config user.email foo@bar.com",
            "git init",
            "git worktree add /tmp/work",
        ]
        for cmd in dangerous_commands:
            assert self.classifier.classify(cmd) == GitSafety.DANGEROUS, f"'{cmd}' should be dangerous"

    def test_non_git_command_is_safe(self) -> None:
        assert self.classifier.classify("echo hello") == GitSafety.SAFE


class TestGitClassifierEvaluate:
    def setup_method(self) -> None:
        self.classifier = GitOperationClassifier()

    def test_non_shell_abstains(self) -> None:
        req = ToolCallRequest(tool="read_file")
        result = self.classifier.evaluate(req)
        assert result.decision == PolicyDecision.ABSTAIN

    def test_non_git_shell_abstains(self) -> None:
        req = ToolCallRequest(tool="bash", command="echo hello")
        result = self.classifier.evaluate(req)
        assert result.decision == PolicyDecision.ABSTAIN

    def test_safe_git_allows(self) -> None:
        req = ToolCallRequest(tool="bash", command="git status")
        result = self.classifier.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_dangerous_git_denies(self) -> None:
        req = ToolCallRequest(tool="bash", command="git push --force origin main")
        result = self.classifier.evaluate(req)
        assert result.decision == PolicyDecision.DENY
