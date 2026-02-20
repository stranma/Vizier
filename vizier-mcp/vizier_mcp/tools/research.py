"""Lightweight on-demand research tool (D69).

Provides research_topic for quick lookups during decomposition,
replacing the heavy DRAFT->SCOUTED round-trip for simple queries.
The full Scout pipeline is preserved for standalone research tasks.
"""


async def research_topic(query: str, depth: str = "shallow") -> dict:
    """Lightweight research on a topic via web search and analysis.

    :param query: The research query.
    :param depth: "shallow" for quick lookups, "deep" for thorough investigation.
    :return: {"findings": list[dict], "summary": str} with structured results.
    """
    raise NotImplementedError
