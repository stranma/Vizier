"""Tests for BaseWorker ABC."""


class TestBaseWorker:
    def test_allowed_tools(self, stub_worker) -> None:
        tools = stub_worker.allowed_tools
        assert "file_read" in tools
        assert "bash" in tools
        assert "git" in tools

    def test_tool_restrictions(self, stub_worker) -> None:
        restrictions = stub_worker.tool_restrictions
        assert "bash" in restrictions
        assert "allowed_patterns" in restrictions["bash"]
        assert "denied_patterns" in restrictions["bash"]

    def test_git_strategy_default(self, stub_worker) -> None:
        assert stub_worker.git_strategy == "branch_per_spec"

    def test_get_prompt(self, stub_worker, sample_spec) -> None:
        prompt = stub_worker.get_prompt(sample_spec, {})
        assert "001-test-feature" in prompt
