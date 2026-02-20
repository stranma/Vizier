"""Pasha support tools (scan specs, assign workers, handle pings)."""


async def orch_scan_specs(project_id: str) -> dict:
    """Scan for specs in a given state within a project.

    :param project_id: Project identifier.
    :return: {"specs": list[dict]} with spec summaries grouped by state.
    """
    raise NotImplementedError


async def orch_check_ready(project_id: str, spec_id: str) -> dict:
    """Check if a spec's dependencies are satisfied and it can be assigned.

    :param project_id: Project identifier.
    :param spec_id: Spec to check.
    :return: {"ready": bool, "blocking": list[str]} with blocking spec IDs if any.
    """
    raise NotImplementedError


async def orch_assign_worker(project_id: str, spec_id: str) -> dict:
    """Assign a Worker to a READY spec and transition it to IN_PROGRESS.

    :param project_id: Project identifier.
    :param spec_id: Spec to assign.
    :return: {"assigned": bool, "worker_session_id": str}.
    """
    raise NotImplementedError


async def orch_write_ping(
    project_id: str,
    spec_id: str,
    urgency: str,
    message: str,
) -> dict:
    """Write a ping from an inner agent to its Pasha.

    :param project_id: Project identifier.
    :param spec_id: Spec context for the ping.
    :param urgency: One of QUESTION, BLOCKER.
    :param message: Description of the issue.
    :return: {"written": bool}.
    """
    raise NotImplementedError
