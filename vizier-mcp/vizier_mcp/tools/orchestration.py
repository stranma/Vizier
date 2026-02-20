"""Pasha support tools (scan specs, assign workers, handle pings)."""


async def orch_scan_specs(project_id: str) -> dict:
    """Scan for specs in a given state within a project.

    :param project_id: Project identifier.
    :return: {"specs": list[dict]} with spec summaries grouped by state.
    """
    raise NotImplementedError


async def orch_check_ready(project_id: str, spec_id: str) -> dict:
    """Check if a spec's dependencies are satisfied and it can be assigned (D79).

    A dependency is "satisfied" only when the dependency spec reaches DONE.
    All other states count as "not satisfied."

    If a blocking dependency is in a terminal failure state (STUCK), the
    response includes a stall_reason field for Pasha to escalate.

    :param project_id: Project identifier.
    :param spec_id: Spec to check.
    :return: {"ready": bool, "blocking": list[str], "stall_reason"?: str}.
             stall_reason is present only when a dependency is STUCK.
    """
    raise NotImplementedError


async def orch_assign_worker(project_id: str, spec_id: str) -> dict:
    """Assign a Worker to a READY spec and transition it to IN_PROGRESS (D76).

    Internally calls orch_check_ready as a guard -- Worker is never spawned
    for a spec with unsatisfied dependencies. Sets claimed_at timestamp
    on the spec for zombie detection.

    :param project_id: Project identifier.
    :param spec_id: Spec to assign.
    :return: {"assigned": bool, "worker_session_id": str, "claimed_at": str}.
    """
    raise NotImplementedError


async def orch_write_ping(
    project_id: str,
    spec_id: str,
    urgency: str,
    message: str,
) -> dict:
    """Write a ping from an inner agent to its Pasha (D77).

    :param project_id: Project identifier.
    :param spec_id: Spec context for the ping.
    :param urgency: One of QUESTION, BLOCKER, IMPOSSIBLE (D77).
                    IMPOSSIBLE means the spec itself is defective.
    :param message: Description of the issue.
    :return: {"written": bool}.
    """
    raise NotImplementedError
