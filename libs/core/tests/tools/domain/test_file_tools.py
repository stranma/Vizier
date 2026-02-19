"""Tests for file operation tools."""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TC003

from vizier.core.tools.domain.file_tools import (
    create_edit_file_tool,
    create_read_file_tool,
    create_write_file_tool,
)
from vizier.core.tools.domain.write_set import WriteSetChecker


class TestReadFile:
    def test_read_existing_file(self, tmp_path: Path) -> None:
        (tmp_path / "hello.txt").write_text("Hello, World!")
        tool = create_read_file_tool(str(tmp_path))
        result = tool.handler(path="hello.txt")
        assert result["content"] == "Hello, World!"
        assert result["size"] == 13

    def test_read_missing_file(self, tmp_path: Path) -> None:
        tool = create_read_file_tool(str(tmp_path))
        result = tool.handler(path="missing.txt")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_read_absolute_path(self, tmp_path: Path) -> None:
        f = tmp_path / "abs.txt"
        f.write_text("absolute")
        tool = create_read_file_tool()
        result = tool.handler(path=str(f))
        assert result["content"] == "absolute"

    def test_json_schema(self) -> None:
        tool = create_read_file_tool()
        assert tool.name == "read_file"
        assert "path" in tool.input_schema["properties"]
        assert "path" in tool.input_schema["required"]


class TestWriteFile:
    def test_write_new_file(self, tmp_path: Path) -> None:
        tool = create_write_file_tool(str(tmp_path))
        result = tool.handler(path="new.txt", content="Hello")
        assert "error" not in result
        assert (tmp_path / "new.txt").read_text() == "Hello"

    def test_write_creates_dirs(self, tmp_path: Path) -> None:
        tool = create_write_file_tool(str(tmp_path))
        result = tool.handler(path="sub/dir/file.py", content="code")
        assert "error" not in result
        assert (tmp_path / "sub" / "dir" / "file.py").read_text() == "code"

    def test_write_denied_by_write_set(self, tmp_path: Path) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        tool = create_write_file_tool(str(tmp_path), write_set=checker)
        result = tool.handler(path="config/settings.yaml", content="data")
        assert "error" in result
        assert "write-set" in result["error"].lower()
        assert not os.path.exists(tmp_path / "config" / "settings.yaml")

    def test_write_allowed_by_write_set(self, tmp_path: Path) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        tool = create_write_file_tool(str(tmp_path), write_set=checker)
        result = tool.handler(path="src/main.py", content="print('hi')")
        assert "error" not in result
        assert (tmp_path / "src" / "main.py").read_text() == "print('hi')"

    def test_json_schema(self) -> None:
        tool = create_write_file_tool()
        assert tool.name == "write_file"
        assert "content" in tool.input_schema["properties"]


class TestEditFile:
    def test_edit_replaces_text(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("def hello():\n    pass\n")
        tool = create_edit_file_tool(str(tmp_path))
        result = tool.handler(path="code.py", old_text="pass", new_text="return 42")
        assert result["replacements"] == 1
        assert (tmp_path / "code.py").read_text() == "def hello():\n    return 42\n"

    def test_edit_text_not_found(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("def hello(): pass")
        tool = create_edit_file_tool(str(tmp_path))
        result = tool.handler(path="code.py", old_text="nonexistent", new_text="x")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_edit_ambiguous_text(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("pass\npass\n")
        tool = create_edit_file_tool(str(tmp_path))
        result = tool.handler(path="code.py", old_text="pass", new_text="return")
        assert "error" in result
        assert "2 times" in result["error"]

    def test_edit_denied_by_write_set(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text("key: value")
        checker = WriteSetChecker(["src/**/*.py"])
        tool = create_edit_file_tool(str(tmp_path), write_set=checker)
        result = tool.handler(path="config.yaml", old_text="value", new_text="new")
        assert "error" in result
        assert "write-set" in result["error"].lower()

    def test_edit_missing_file(self, tmp_path: Path) -> None:
        tool = create_edit_file_tool(str(tmp_path))
        result = tool.handler(path="missing.py", old_text="x", new_text="y")
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_edit_file_tool()
        assert tool.name == "edit_file"
        assert "old_text" in tool.input_schema["properties"]
        assert "new_text" in tool.input_schema["properties"]
