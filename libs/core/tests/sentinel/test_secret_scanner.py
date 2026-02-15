"""Tests for secret scanner."""

from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest
from vizier.core.sentinel.secret_scanner import SecretScanner


class TestSecretScanner:
    def setup_method(self) -> None:
        self.scanner = SecretScanner()

    def test_aws_access_key_detected(self) -> None:
        req = ToolCallRequest(tool="bash", command="export AWS_KEY=AKIAIOSFODNN7EXAMPLE")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.DENY
        assert "AWS" in result.reason

    def test_api_key_assignment_detected(self) -> None:
        req = ToolCallRequest(tool="bash", command="ANTHROPIC_API_KEY=sk-ant-1234567890abcdef")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.DENY

    def test_password_detected(self) -> None:
        req = ToolCallRequest(tool="bash", command="password=mysecretpassword123")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.DENY

    def test_private_key_detected(self) -> None:
        req = ToolCallRequest(tool="file_write", args={"content": "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."})
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.DENY

    def test_github_token_detected(self) -> None:
        req = ToolCallRequest(tool="bash", command="export TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.DENY

    def test_clean_command_abstains(self) -> None:
        req = ToolCallRequest(tool="bash", command="echo hello world")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.ABSTAIN

    def test_empty_request_abstains(self) -> None:
        req = ToolCallRequest(tool="read_file")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.ABSTAIN

    def test_bearer_token_detected(self) -> None:
        req = ToolCallRequest(tool="bash", command="auth_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.test")
        result = self.scanner.scan(req)
        assert result.decision == PolicyDecision.DENY
