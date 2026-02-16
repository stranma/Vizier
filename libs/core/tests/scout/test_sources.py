"""Tests for Scout search sources."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vizier.core.scout.sources import (
    GitHubSearchSource,
    NpmSearchSource,
    PyPISearchSource,
    SearchResult,
    search_all,
)


class TestGitHubSearchSource:
    def test_search_parses_gh_output(self) -> None:
        mock_executor = MagicMock()
        mock_executor.execute.return_value = json.dumps(
            [
                {
                    "name": "fastapi",
                    "url": "https://github.com/tiangolo/fastapi",
                    "description": "FastAPI framework",
                    "stargazersCount": 70000,
                    "licenseInfo": {"name": "MIT License"},
                },
            ]
        )
        source = GitHubSearchSource(tool_executor=mock_executor)
        results = source.search("python web framework")
        assert len(results) == 1
        assert results[0].name == "fastapi"
        assert results[0].source == "github"
        assert results[0].license == "MIT License"
        assert "70000" in results[0].metric

    def test_search_handles_no_executor(self) -> None:
        source = GitHubSearchSource(tool_executor=None)
        results = source.search("test query")
        assert results == []

    def test_search_handles_executor_error(self) -> None:
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = RuntimeError("gh not found")
        source = GitHubSearchSource(tool_executor=mock_executor)
        results = source.search("test query")
        assert results == []

    def test_search_handles_empty_license_info(self) -> None:
        mock_executor = MagicMock()
        mock_executor.execute.return_value = json.dumps(
            [
                {
                    "name": "some-repo",
                    "url": "https://github.com/user/some-repo",
                    "description": "A repo",
                    "stargazersCount": 10,
                    "licenseInfo": None,
                },
            ]
        )
        source = GitHubSearchSource(tool_executor=mock_executor)
        results = source.search("test")
        assert len(results) == 1
        assert results[0].license == ""


class TestPyPISearchSource:
    def test_search_parses_pypi_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "info": {
                "name": "requests",
                "summary": "Python HTTP library",
                "project_url": "https://pypi.org/project/requests/",
                "license": "Apache-2.0",
                "version": "2.31.0",
            },
        }
        with patch("httpx.get", return_value=mock_response) as mock_get:
            source = PyPISearchSource()
            results = source.search("requests")
            assert len(results) == 1
            assert results[0].name == "requests"
            assert results[0].source == "pypi"
            assert results[0].license == "Apache-2.0"
            mock_get.assert_called_once()

    def test_search_handles_404(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("httpx.get", return_value=mock_response):
            source = PyPISearchSource()
            results = source.search("nonexistent-package")
            assert results == []

    def test_search_handles_network_error(self) -> None:
        with patch("httpx.get", side_effect=ConnectionError("timeout")):
            source = PyPISearchSource()
            results = source.search("test")
            assert results == []


class TestNpmSearchSource:
    def test_search_parses_npm_response(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "objects": [
                {
                    "package": {
                        "name": "express",
                        "description": "Fast web framework",
                        "version": "4.18.2",
                        "license": "MIT",
                        "links": {"npm": "https://www.npmjs.com/package/express"},
                    },
                },
            ],
        }
        with patch("httpx.get", return_value=mock_response):
            source = NpmSearchSource()
            results = source.search("web framework")
            assert len(results) == 1
            assert results[0].name == "express"
            assert results[0].source == "npm"
            assert results[0].license == "MIT"

    def test_search_handles_network_error(self) -> None:
        with patch("httpx.get", side_effect=ConnectionError("timeout")):
            source = NpmSearchSource()
            results = source.search("test")
            assert results == []


class TestSearchAll:
    def test_deduplicates_by_url(self) -> None:
        source1 = MagicMock()
        source1.search.return_value = [
            SearchResult(name="pkg", url="https://example.com/pkg", source="github"),
        ]
        source2 = MagicMock()
        source2.search.return_value = [
            SearchResult(name="pkg", url="https://example.com/pkg", source="pypi"),
        ]
        results = search_all(["test"], [source1, source2])
        assert len(results) == 1
        assert results[0].source == "github"

    def test_combines_multiple_queries(self) -> None:
        source = MagicMock()
        source.search.side_effect = [
            [SearchResult(name="a", url="https://a.com", source="github")],
            [SearchResult(name="b", url="https://b.com", source="github")],
        ]
        results = search_all(["q1", "q2"], [source])
        assert len(results) == 2
        assert source.search.call_count == 2

    def test_handles_source_error(self) -> None:
        source = MagicMock()
        source.search.side_effect = RuntimeError("fail")
        results = search_all(["test"], [source])
        assert results == []

    def test_empty_queries(self) -> None:
        source = MagicMock()
        results = search_all([], [source])
        assert results == []
        source.search.assert_not_called()

    def test_empty_sources(self) -> None:
        results = search_all(["test"], [])
        assert results == []
