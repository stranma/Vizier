"""Scout search sources: GitHub, PyPI, npm."""

from __future__ import annotations

import json
import logging
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote as url_quote

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from any source."""

    name: str
    url: str
    source: str
    description: str = ""
    license: str = ""
    metric: str = ""
    relevance: str = "MEDIUM"


class SearchSource(ABC):
    """Abstract base for search sources."""

    @abstractmethod
    def search(self, query: str) -> list[SearchResult]:
        """Run a search query and return results.

        :param query: Search query string.
        :returns: List of search results.
        """
        ...


class GitHubSearchSource(SearchSource):
    """Search GitHub repositories and code via the gh CLI."""

    def __init__(self, tool_executor: Any = None) -> None:
        self._executor = tool_executor

    def search(self, query: str) -> list[SearchResult]:
        """Search GitHub repos using gh CLI via ToolExecutor.

        :param query: Search query string.
        :returns: List of search results from GitHub.
        """
        if self._executor is None:
            logger.debug("No tool executor available for GitHub search")
            return []

        results: list[SearchResult] = []
        try:
            safe_query = shlex.quote(query)
            cmd = f"gh search repos {safe_query} --json name,url,description,stargazersCount,licenseInfo --limit 10"
            output = self._executor.execute("bash", cmd)
            if output and isinstance(output, str):
                repos = json.loads(output)
                for repo in repos:
                    license_name = ""
                    license_info = repo.get("licenseInfo")
                    if isinstance(license_info, dict):
                        license_name = license_info.get("name", "")
                    results.append(
                        SearchResult(
                            name=repo.get("name", ""),
                            url=repo.get("url", ""),
                            source="github",
                            description=repo.get("description", "") or "",
                            license=license_name,
                            metric=f"{repo.get('stargazersCount', 0)} stars",
                        )
                    )
        except Exception:
            logger.debug("GitHub search failed for query: %s", query, exc_info=True)

        return results


class PyPISearchSource(SearchSource):
    """Search PyPI packages via the JSON API."""

    def search(self, query: str) -> list[SearchResult]:
        """Search PyPI for packages matching the query.

        Uses the PyPI JSON API to look up a package by exact name.

        :param query: Package name to search for.
        :returns: List of search results from PyPI.
        """
        results: list[SearchResult] = []
        try:
            import httpx

            terms = url_quote(query.lower().replace(" ", "-"), safe="")
            resp = httpx.get(f"https://pypi.org/pypi/{terms}/json", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                info = data.get("info", {})
                results.append(
                    SearchResult(
                        name=info.get("name", terms),
                        url=info.get("project_url", f"https://pypi.org/project/{terms}/"),
                        source="pypi",
                        description=info.get("summary", ""),
                        license=info.get("license", "") or "",
                        metric=info.get("version", ""),
                    )
                )
        except Exception:
            logger.debug("PyPI search failed for query: %s", query, exc_info=True)

        return results


class NpmSearchSource(SearchSource):
    """Search npm packages via the registry API."""

    def search(self, query: str) -> list[SearchResult]:
        """Search npm registry for packages matching the query.

        :param query: Search query string.
        :returns: List of search results from npm.
        """
        results: list[SearchResult] = []
        try:
            import httpx

            safe_text = url_quote(query, safe="")
            resp = httpx.get(
                f"https://registry.npmjs.org/-/v1/search?text={safe_text}&size=10",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for obj in data.get("objects", []):
                    pkg = obj.get("package", {})
                    links = pkg.get("links", {})
                    results.append(
                        SearchResult(
                            name=pkg.get("name", ""),
                            url=links.get("npm", links.get("homepage", "")),
                            source="npm",
                            description=pkg.get("description", ""),
                            license=pkg.get("license", "") if isinstance(pkg.get("license"), str) else "",
                            metric=pkg.get("version", ""),
                        )
                    )
        except Exception:
            logger.debug("npm search failed for query: %s", query, exc_info=True)

        return results


@dataclass
class SearchAggregator:
    """Aggregates results from multiple sources, deduplicating by URL."""

    sources: list[SearchSource] = field(default_factory=list)

    def search_all(self, queries: list[str]) -> list[SearchResult]:
        """Run all queries across all sources and deduplicate.

        :param queries: List of search queries.
        :returns: Deduplicated list of search results.
        """
        return search_all(queries, self.sources)


def search_all(queries: list[str], sources: list[SearchSource]) -> list[SearchResult]:
    """Run all queries across all sources and deduplicate by URL.

    :param queries: List of search queries.
    :param sources: List of search sources to query.
    :returns: Deduplicated list of search results.
    """
    seen_urls: set[str] = set()
    results: list[SearchResult] = []

    for query in queries:
        for source in sources:
            try:
                for result in source.search(query):
                    if result.url and result.url not in seen_urls:
                        seen_urls.add(result.url)
                        results.append(result)
            except Exception:
                logger.debug("Search source %s failed for query: %s", type(source).__name__, query, exc_info=True)

    return results
