"""Tests for search tools (glob, grep)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.tools.domain.search_tools import create_glob_tool, create_grep_tool


class TestGlob:
    def test_find_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("")
        (tmp_path / "utils.py").write_text("")
        (tmp_path / "readme.md").write_text("")
        tool = create_glob_tool(str(tmp_path))
        result = tool.handler(pattern="*.py")
        assert "error" not in result
        assert len(result["matches"]) == 2
        assert result["total"] == 2

    def test_recursive_glob(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("")
        (tmp_path / "src" / "sub").mkdir()
        (tmp_path / "src" / "sub" / "b.py").write_text("")
        tool = create_glob_tool(str(tmp_path))
        result = tool.handler(pattern="**/*.py")
        assert result["total"] >= 2

    def test_no_matches(self, tmp_path: Path) -> None:
        tool = create_glob_tool(str(tmp_path))
        result = tool.handler(pattern="*.rs")
        assert result["total"] == 0
        assert result["matches"] == []

    def test_invalid_directory(self) -> None:
        tool = create_glob_tool("/nonexistent/path/12345")
        result = tool.handler(pattern="*.py")
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_glob_tool()
        assert tool.name == "glob"
        assert "pattern" in tool.input_schema["properties"]
        assert "pattern" in tool.input_schema["required"]


class TestGrep:
    def test_find_pattern_in_files(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("def hello():\n    return 42\n")
        (tmp_path / "other.py").write_text("x = 1\ny = 2\n")
        tool = create_grep_tool(str(tmp_path))
        result = tool.handler(pattern="def ")
        assert "error" not in result
        assert result["total"] == 1
        assert result["matches"][0]["file"] == "code.py"
        assert result["matches"][0]["line"] == 1

    def test_regex_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("count = 42\nresult = count + 1\n")
        tool = create_grep_tool(str(tmp_path))
        result = tool.handler(pattern=r"count\s*=")
        assert result["total"] == 1

    def test_file_pattern_filter(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("hello\n")
        (tmp_path / "code.js").write_text("hello\n")
        tool = create_grep_tool(str(tmp_path))
        result = tool.handler(pattern="hello", file_pattern="*.py")
        assert result["total"] == 1
        assert result["matches"][0]["file"] == "code.py"

    def test_invalid_regex(self, tmp_path: Path) -> None:
        tool = create_grep_tool(str(tmp_path))
        result = tool.handler(pattern="[invalid")
        assert "error" in result
        assert "regex" in result["error"].lower()

    def test_no_matches(self, tmp_path: Path) -> None:
        (tmp_path / "code.py").write_text("hello\n")
        tool = create_grep_tool(str(tmp_path))
        result = tool.handler(pattern="nonexistent_pattern_xyz")
        assert result["total"] == 0

    def test_json_schema(self) -> None:
        tool = create_grep_tool()
        assert tool.name == "grep"
        assert "pattern" in tool.input_schema["properties"]
