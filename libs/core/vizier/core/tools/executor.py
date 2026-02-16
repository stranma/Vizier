"""Tool executor: runs subprocesses with scoped secret injection."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

from vizier.core.secrets.store import SecretStore  # noqa: TC001

logger = logging.getLogger(__name__)

DEFAULT_TOOL_SECRETS: dict[str, list[str]] = {
    "git": ["GITHUB_TOKEN", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL"],
    "bash": [],
}


class ToolExecutor:
    """Executes tool commands with scoped secret injection.

    When running a subprocess, only the secrets explicitly allowed for that
    tool type are injected into the subprocess environment. The secrets exist
    only for the lifetime of the subprocess.

    :param store: Secret store to retrieve secret values from.
    :param tool_secrets: Mapping of tool type to allowed secret keys.
    """

    def __init__(
        self,
        store: SecretStore,
        tool_secrets: dict[str, list[str]] | None = None,
    ) -> None:
        self._store = store
        self._tool_secrets = tool_secrets or dict(DEFAULT_TOOL_SECRETS)

    def execute_command(
        self,
        command: str,
        *,
        tool_type: str = "bash",
        extra_secrets: list[str] | None = None,
        timeout: int = 120,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a command with scoped secret injection.

        :param command: Shell command to execute.
        :param tool_type: Tool type for secret scoping (e.g. "git", "bash").
        :param extra_secrets: Additional secret keys to inject beyond the tool default.
        :param timeout: Command timeout in seconds.
        :param cwd: Working directory for the command.
        :returns: CompletedProcess result.
        """
        env = self._build_env(tool_type, extra_secrets)

        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )

    def _build_env(self, tool_type: str, extra_secrets: list[str] | None = None) -> dict[str, str]:
        """Build subprocess environment with scoped secrets.

        :param tool_type: Tool type for secret scoping.
        :param extra_secrets: Additional secret keys to inject.
        :returns: Environment dict for the subprocess.
        """
        env = dict(os.environ)

        allowed_keys = list(self._tool_secrets.get(tool_type, []))
        if extra_secrets:
            allowed_keys.extend(extra_secrets)

        injected = 0
        for key in allowed_keys:
            value = self._store.get(key)
            if value:
                env[key] = value
                injected += 1

        if injected > 0:
            logger.debug("Injected %d secrets for tool_type=%s", injected, tool_type)

        return env

    def get_allowed_secrets(self, tool_type: str) -> list[str]:
        """Return the list of secret keys allowed for a tool type.

        :param tool_type: Tool type name.
        :returns: List of allowed secret key names.
        """
        return list(self._tool_secrets.get(tool_type, []))

    def configure_tool_secrets(self, tool_type: str, secret_keys: list[str]) -> None:
        """Configure which secrets a tool type can access.

        :param tool_type: Tool type name.
        :param secret_keys: List of secret key names to allow.
        """
        self._tool_secrets[tool_type] = list(secret_keys)

    def to_tool_result(self, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        """Convert a CompletedProcess to a tool result dict.

        :param result: Subprocess result.
        :returns: Dict with stdout, stderr, and return_code.
        """
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
