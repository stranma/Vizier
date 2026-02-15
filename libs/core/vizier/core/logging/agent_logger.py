"""Agent invocation logger: appends JSONL entries to agent-log.jsonl."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from vizier.core.models.logging import AgentLogEntry


class AgentLogger:
    """Appends structured log entries to a JSONL file.

    :param log_path: Path to the agent-log.jsonl file.
    """

    def __init__(self, log_path: str | Path) -> None:
        self._log_path = Path(log_path)

    @property
    def log_path(self) -> Path:
        return self._log_path

    def log(self, entry: AgentLogEntry) -> None:
        """Append a log entry to the JSONL file.

        :param entry: The agent log entry to persist.
        """
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.model_dump(mode="json"), default=str) + "\n")

    def read_entries(self) -> list[AgentLogEntry]:
        """Read all log entries from the JSONL file.

        :returns: List of all logged entries.
        """
        if not self._log_path.exists():
            return []

        entries: list[AgentLogEntry] = []
        with open(self._log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(AgentLogEntry.model_validate(json.loads(line)))
        return entries

    @staticmethod
    def entry_from_litellm_response(
        response: dict,
        agent: str,
        model: str,
        duration_ms: int,
        project: str = "",
        spec_id: str | None = None,
        result: str = "",
    ) -> AgentLogEntry:
        """Extract log entry fields from a LiteLLM response dict.

        :param response: The LiteLLM completion response (or mock thereof).
        :param agent: Agent role name.
        :param model: Model identifier used.
        :param duration_ms: Wall-clock duration of the LLM call.
        :param project: Project name.
        :param spec_id: Spec ID if applicable.
        :param result: Outcome (e.g. "REVIEW", "DONE").
        :returns: Populated AgentLogEntry.
        """
        usage = response.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        cost_usd = response.get("_hidden_params", {}).get("response_cost", 0.0)
        if cost_usd == 0.0:
            cost_usd = response.get("response_cost", 0.0)

        return AgentLogEntry(
            timestamp=datetime.utcnow(),
            agent=agent,
            spec_id=spec_id,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            result=result,
            project=project,
        )
