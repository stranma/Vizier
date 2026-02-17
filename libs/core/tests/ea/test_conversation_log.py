"""Tests for EA conversation log."""

from pathlib import Path

from vizier.core.ea.conversation_log import ConversationLog, ConversationTurn


class TestConversationLog:
    def test_append_and_recent(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path)
        log.append(ConversationTurn(role="user", content="Hello"))
        log.append(ConversationTurn(role="assistant", content="Hi there"))

        turns = log.recent()
        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[0].content == "Hello"
        assert turns[1].role == "assistant"
        assert turns[1].content == "Hi there"

    def test_recent_limits_count(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path)
        for i in range(20):
            log.append(ConversationTurn(role="user", content=f"Message {i}"))

        turns = log.recent(5)
        assert len(turns) == 5
        assert turns[0].content == "Message 15"
        assert turns[4].content == "Message 19"

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        log1 = ConversationLog(tmp_path)
        log1.append(ConversationTurn(role="user", content="Remember this"))
        log1.append(ConversationTurn(role="assistant", content="I will remember"))

        log2 = ConversationLog(tmp_path)
        turns = log2.recent()
        assert len(turns) == 2
        assert turns[0].content == "Remember this"

    def test_empty_log(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path)
        turns = log.recent()
        assert turns == []

    def test_rotation(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path)
        for i in range(1001):
            log.append(ConversationTurn(role="user", content=f"msg {i}"))

        log_path = tmp_path / "conversation.jsonl"
        backup_path = tmp_path / "conversation.jsonl.1"
        assert log_path.exists()
        assert backup_path.exists()

        current_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(current_lines) == 1

    def test_corrupt_line_skipped(self, tmp_path: Path) -> None:
        log_path = tmp_path / "conversation.jsonl"
        log_path.write_text(
            '{"timestamp":"2026-01-01T00:00:00","role":"user","content":"valid","category":"","metadata":{}}\n'
            "NOT VALID JSON\n"
            '{"timestamp":"2026-01-01T00:00:01","role":"assistant","content":"also valid","category":"","metadata":{}}\n',
            encoding="utf-8",
        )

        log = ConversationLog(tmp_path)
        turns = log.recent()
        assert len(turns) == 2
        assert turns[0].content == "valid"
        assert turns[1].content == "also valid"

    def test_category_stored(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path)
        log.append(ConversationTurn(role="user", content="Hello", category="general"))

        turns = log.recent()
        assert turns[0].category == "general"

    def test_metadata_stored(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path)
        log.append(ConversationTurn(role="user", content="Hello", metadata={"reply_to": "previous msg"}))

        turns = log.recent()
        assert turns[0].metadata["reply_to"] == "previous msg"

    def test_max_turns_default(self, tmp_path: Path) -> None:
        log = ConversationLog(tmp_path, max_turns=3)
        for i in range(10):
            log.append(ConversationTurn(role="user", content=f"msg {i}"))

        turns = log.recent()
        assert len(turns) == 3
        assert turns[0].content == "msg 7"
