"""Pasha support tools (scan specs, assign workers, handle pings).

Includes the learnings injection tool (D70) for enriching agent spawn context.
"""


async def get_relevant_learnings(
    project_id: str,
    spec_id: str | None = None,
    agent_role: str | None = None,
) -> dict:
    """Get learnings relevant to a spec and/or agent role (D70).

    Searches the project's learnings.md for entries matching the spec's
    context (title, artifacts, domain) and the agent role. Pasha calls
    this before spawning any agent and includes results in spawn context.

    :param project_id: Project identifier.
    :param spec_id: Optional spec ID for context-aware matching.
    :param agent_role: Optional agent role to filter role-specific learnings.
    :return: {"learnings": list[str]} with relevant learning entries.
    """
    raise NotImplementedError
