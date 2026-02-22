"""Sentinel security enforcement tools (v1).

Provides sentinel_check_write for file write validation, plus the
Sentinel-wrapped execution tools (D67, D78): run_command_checked and
web_fetch_checked. Error contract clarified by D78.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import httpx

from vizier_mcp.models.sentinel import PolicyDecision
from vizier_mcp.secrets import get_secret
from vizier_mcp.sentinel.haiku import LLMCallable
from vizier_mcp.sentinel.haiku import evaluate_command as haiku_evaluate
from vizier_mcp.sentinel.injection import scan_for_injection
from vizier_mcp.sentinel.policy import (
    check_role_permission,
    load_policy,
    resolve_secret_scopes,
)
from vizier_mcp.sentinel.policy import (
    evaluate_command as evaluate_command_policy,
)
from vizier_mcp.sentinel.write_set import WriteSetChecker

_SAFE_ENV_VARS = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "USER", "SHELL", "TMPDIR", "TZ")

if TYPE_CHECKING:
    from vizier_mcp.config import ServerConfig

logger = logging.getLogger(__name__)


def _build_scoped_env(secret_names: list[str]) -> dict[str, str]:
    """Build a minimal environment with safe vars and requested secrets only.

    :param secret_names: Environment variable names to inject (from resolve_secret_scopes).
    :return: Environment dict with safe vars + resolved secrets.
    """
    env: dict[str, str] = {}
    for k in _SAFE_ENV_VARS:
        v = os.environ.get(k)
        if v is not None:
            env[k] = v
    for name in secret_names:
        value = get_secret(name)
        if value is not None:
            env[name] = value
    return env


def sentinel_check_write(
    config: ServerConfig,
    project_id: str,
    file_path: str,
    agent_role: str,
) -> dict:
    """Validate a file write against Sentinel policy.

    Checks the file path against the project's write-set glob patterns.
    Also checks role_permissions for can_write.

    :param config: Server configuration.
    :param project_id: Project identifier for loading Sentinel policy.
    :param file_path: Target file path (relative to project root).
    :param agent_role: The calling agent's role.
    :return: {"allowed": bool, "reason"?: str}
    """
    policy_result = load_policy(config, project_id)
    if isinstance(policy_result, dict):
        return {"allowed": False, "reason": policy_result.get("error", "Policy load failed")}

    policy = policy_result

    if policy.role_permissions and not check_role_permission(policy, agent_role, "can_write"):
        return {"allowed": False, "reason": f"Role '{agent_role}' does not have write permission"}

    checker = WriteSetChecker(policy.write_set)
    if checker.is_allowed(file_path):
        return {"allowed": True}
    else:
        return {"allowed": False, "reason": f"Path '{file_path}' not in write-set"}


async def run_command_checked(
    config: ServerConfig,
    project_id: str,
    command: str,
    agent_role: str,
    llm_callable: LLMCallable | None = None,
) -> dict:
    """Execute a shell command after Sentinel validation (D67, D78).

    All agent shell commands MUST go through this tool. Native bash/exec is
    blocked by OpenClaw tool policy -- this is the only way to run commands.

    Three return shapes (D78):
    - Denied: {"allowed": False, "reason": str}
    - Succeeded: {"allowed": True, "exit_code": 0, "stdout": str, "stderr": str}
    - Failed: {"allowed": True, "exit_code": N, "stdout": str, "stderr": str}

    :param config: Server configuration.
    :param project_id: Project identifier for loading Sentinel policy.
    :param command: The shell command to execute.
    :param agent_role: The calling agent's role.
    :param llm_callable: Optional LLM callable for Haiku evaluation (injected for testing).
    :return: One of the three D78 shapes.
    """
    policy_result = load_policy(config, project_id)
    if isinstance(policy_result, dict):
        return {"allowed": False, "reason": policy_result.get("error", "Policy load failed")}

    policy = policy_result

    if policy.role_permissions and not check_role_permission(policy, agent_role, "can_bash"):
        return {"allowed": False, "reason": f"Role '{agent_role}' does not have bash permission"}

    decision, reason = evaluate_command_policy(policy, command)

    if decision == PolicyDecision.DENY:
        return {"allowed": False, "reason": reason}

    if decision == PolicyDecision.ABSTAIN:
        if llm_callable is None:
            return {"allowed": False, "reason": "No Haiku evaluator configured (fail-closed)"}

        verdict = await haiku_evaluate(
            command=command,
            agent_role=agent_role,
            llm_callable=llm_callable,
            model=config.sentinel.haiku_model,
        )
        if verdict.decision == PolicyDecision.DENY:
            return {"allowed": False, "reason": verdict.reason}

    secret_names = resolve_secret_scopes(policy, command)
    scoped_env = _build_scoped_env(secret_names)
    return await _execute_command(command, env=scoped_env)


async def _execute_command(command: str, env: dict[str, str] | None = None) -> dict:
    """Execute a shell command and return D78-shaped result.

    :param command: The shell command to execute.
    :param env: Environment variables for the subprocess. If None, inherits parent.
    :return: {"allowed": True, "exit_code": int, "stdout": str, "stderr": str}
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return {
            "allowed": True,
            "exit_code": proc.returncode if proc.returncode is not None else 0,
            "stdout": stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
        }
    except OSError as exc:
        return {
            "allowed": True,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
        }


async def web_fetch_checked(
    config: ServerConfig,
    project_id: str,
    url: str,
    agent_role: str,
) -> dict:
    """Fetch a URL and scan content for prompt injection (D67, D78).

    All agent web fetches MUST go through this tool. Native web_fetch is
    blocked by OpenClaw tool policy -- this is the only way to fetch URLs.

    Three return shapes (D78):
    - Blocked: {"safe": False, "reason": str}
    - Fetched: {"safe": True, "content": str, "status_code": 200}
    - Failed: {"safe": True, "content": "", "status_code": N, "error": str}

    :param config: Server configuration.
    :param project_id: Project identifier for loading Sentinel policy.
    :param url: The URL to fetch.
    :param agent_role: The calling agent's role.
    :return: One of the three D78 shapes.
    """
    policy_result = load_policy(config, project_id)
    if isinstance(policy_result, dict):
        return {"safe": False, "reason": policy_result.get("error", "Policy load failed")}

    policy = policy_result

    if policy.role_permissions and not check_role_permission(policy, agent_role, "can_web_fetch"):
        return {"safe": False, "reason": f"Role '{agent_role}' does not have web_fetch permission"}

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
    except (httpx.HTTPError, OSError) as exc:
        return {
            "safe": True,
            "content": "",
            "status_code": 0,
            "error": str(exc),
        }

    if response.status_code >= 400:
        return {
            "safe": True,
            "content": "",
            "status_code": response.status_code,
            "error": f"HTTP {response.status_code}",
        }

    content = response.text
    injection_reason = scan_for_injection(content)
    if injection_reason:
        return {"safe": False, "reason": injection_reason}

    return {
        "safe": True,
        "content": content,
        "status_code": response.status_code,
    }


def secret_check(name: str) -> dict:
    """Check whether a named secret is available (without revealing its value).

    :param name: The environment variable name (e.g. ``GITHUB_TOKEN``).
    :return: {"name": str, "exists": bool}
    """
    value = get_secret(name)
    return {"name": name, "exists": value is not None}
