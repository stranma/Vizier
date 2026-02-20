"""Sentinel security enforcement tools (v1).

Provides sentinel_check_write for file write validation, plus the
Sentinel-wrapped execution tools (D67): run_command_checked and
web_fetch_checked.
"""


async def sentinel_check_write(
    project_id: str,
    file_path: str,
    content: str,
    agent_role: str,
) -> dict:
    """Validate a file write against Sentinel policy.

    Checks the write against the project's allowlist/denylist rules and,
    if ambiguous, delegates to Haiku for classification.

    :param project_id: Project identifier for loading Sentinel policy.
    :param file_path: Target file path.
    :param content: Proposed file content.
    :param agent_role: The calling agent's role.
    :return: {"allowed": bool, "reason": str}.
    """
    raise NotImplementedError


async def run_command_checked(project_id: str, command: str, agent_role: str) -> dict:
    """Execute a shell command after Sentinel validation (D67).

    All agent shell commands MUST go through this tool. Native bash/exec is
    blocked by OpenClaw tool policy -- this is the only way to run commands.

    :param project_id: Project identifier for loading Sentinel policy.
    :param command: The shell command to execute.
    :param agent_role: The calling agent's role (worker, quality_gate, etc.).
    :return: {"allowed": bool, "output": str, "exit_code": int} or denial reason.
    """
    raise NotImplementedError


async def web_fetch_checked(url: str, agent_role: str) -> dict:
    """Fetch a URL and scan content for prompt injection (D67).

    All agent web fetches MUST go through this tool. Native web_fetch is
    blocked by OpenClaw tool policy -- this is the only way to fetch URLs.

    :param url: The URL to fetch.
    :param agent_role: The calling agent's role.
    :return: {"safe": bool, "content": str} or {"safe": False, "reason": str}.
    """
    raise NotImplementedError
