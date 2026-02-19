"""Pasha event loop: processes spec lifecycle events and pings.

Integrates adaptive reconciliation (D58), ping handling (D50),
DAG-aware scheduling (D52), and evidence completeness checking (D56).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from vizier.core.scheduling.dag_validator import DagNode, DagValidationError, validate_dag
from vizier.core.scheduling.evidence_checker import EvidenceChecker, get_required_evidence
from vizier.core.watcher.adaptive import AdaptiveConfig, AdaptiveReconciler

logger = logging.getLogger(__name__)


@dataclass
class PingEvent:
    """A ping event from an agent.

    :param spec_id: Spec identifier.
    :param urgency: Ping urgency (INFO, QUESTION, BLOCKER).
    :param message: Ping message content.
    :param file_path: Path to the ping file.
    """

    spec_id: str
    urgency: str
    message: str
    file_path: str


@dataclass
class SpecEvent:
    """A spec lifecycle event.

    :param spec_id: Spec identifier.
    :param status: Current spec status.
    :param event_type: Type of event (status_change, new_spec, ping).
    """

    spec_id: str
    status: str
    event_type: str


@dataclass
class EventLoopState:
    """State tracked by the Pasha event loop.

    :param active_specs: Set of spec IDs currently being processed.
    :param pending_pings: Queue of unprocessed ping events.
    :param cycle_count: Number of reconciliation cycles completed.
    """

    active_specs: set[str] = field(default_factory=set)
    pending_pings: list[PingEvent] = field(default_factory=list)
    cycle_count: int = 0


class PashaEventLoop:
    """Processes spec lifecycle events with adaptive reconciliation.

    :param project_root: Project root directory.
    :param plugin_name: Plugin name for evidence type resolution.
    :param adaptive_config: Configuration for adaptive reconciliation.
    """

    def __init__(
        self,
        *,
        project_root: str,
        plugin_name: str = "software",
        adaptive_config: AdaptiveConfig | None = None,
    ) -> None:
        self._project_root = project_root
        self._plugin_name = plugin_name
        self._reconciler = AdaptiveReconciler(adaptive_config or AdaptiveConfig())
        self._state = EventLoopState()

    @property
    def state(self) -> EventLoopState:
        """Access the event loop state."""
        return self._state

    @property
    def reconciler(self) -> AdaptiveReconciler:
        """Access the adaptive reconciler."""
        return self._reconciler

    def scan_pings(self) -> list[PingEvent]:
        """Scan for unprocessed ping files in spec directories.

        :returns: List of new ping events found.
        """
        pings: list[PingEvent] = []
        specs_dir = os.path.join(self._project_root, ".vizier", "specs")
        if not os.path.isdir(specs_dir):
            return pings

        for spec_id in os.listdir(specs_dir):
            ping_dir = os.path.join(specs_dir, spec_id, "pings")
            if not os.path.isdir(ping_dir):
                continue
            for filename in sorted(os.listdir(ping_dir)):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(ping_dir, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        data = json.load(f)
                    pings.append(
                        PingEvent(
                            spec_id=spec_id,
                            urgency=data.get("urgency", "INFO"),
                            message=data.get("message", ""),
                            file_path=filepath,
                        )
                    )
                except (json.JSONDecodeError, OSError):
                    continue

        return pings

    def process_pings(self, pings: list[PingEvent]) -> list[dict[str, Any]]:
        """Process ping events by urgency.

        Returns a list of action records for each ping processed.

        :param pings: List of ping events to process.
        :returns: List of action records.
        """
        actions: list[dict[str, Any]] = []
        for ping in pings:
            action: dict[str, Any] = {
                "spec_id": ping.spec_id,
                "urgency": ping.urgency,
                "message": ping.message,
            }
            if ping.urgency == "BLOCKER":
                action["action"] = "escalate_to_ea"
                action["immediate"] = True
            elif ping.urgency == "QUESTION":
                action["action"] = "process_immediately"
                action["immediate"] = True
            else:
                action["action"] = "note_for_report"
                action["immediate"] = False
            actions.append(action)

        return actions

    def scan_specs(self) -> list[SpecEvent]:
        """Scan all specs and return their current states.

        :returns: List of spec events with current status.
        """
        events: list[SpecEvent] = []
        specs_dir = os.path.join(self._project_root, ".vizier", "specs")
        if not os.path.isdir(specs_dir):
            return events

        for spec_id in sorted(os.listdir(specs_dir)):
            state_path = os.path.join(specs_dir, spec_id, "state.json")
            if not os.path.isfile(state_path):
                continue
            try:
                with open(state_path, encoding="utf-8") as f:
                    state = json.load(f)
                events.append(
                    SpecEvent(
                        spec_id=spec_id,
                        status=state.get("status", "UNKNOWN"),
                        event_type="status_check",
                    )
                )
            except (json.JSONDecodeError, OSError):
                continue

        return events

    def check_dag_validity(self, nodes: list[DagNode]) -> tuple[bool, list[str] | str]:
        """Validate a dependency DAG from a PROPOSE_PLAN.

        :param nodes: List of DAG nodes with dependency info.
        :returns: Tuple of (valid, topological_order_or_error_message).
        """
        try:
            order = validate_dag(nodes)
            return True, order
        except DagValidationError as e:
            return False, str(e)

    def check_evidence_completeness(self, spec_id: str) -> tuple[bool, list[str]]:
        """Check if all required evidence exists for a spec.

        :param spec_id: Spec identifier.
        :returns: Tuple of (complete, missing_types).
        """
        evidence_dir = os.path.join(self._project_root, ".vizier", "specs", spec_id, "evidence")
        required = get_required_evidence(self._plugin_name)
        checker = EvidenceChecker(required, evidence_dir)
        result = checker.check()
        return result.complete, result.missing

    def specs_ready_for_assignment(self, specs: list[SpecEvent], completed: set[str]) -> list[str]:
        """Find READY specs whose dependencies are all DONE.

        :param specs: List of spec events.
        :param completed: Set of completed spec IDs.
        :returns: List of spec IDs ready for Worker assignment.
        """
        ready: list[str] = []
        specs_dir = os.path.join(self._project_root, ".vizier", "specs")

        for spec in specs:
            if spec.status != "READY":
                continue
            state_path = os.path.join(specs_dir, spec.spec_id, "state.json")
            try:
                with open(state_path, encoding="utf-8") as f:
                    state = json.load(f)
                depends_on = state.get("depends_on", [])
                if all(dep in completed for dep in depends_on):
                    ready.append(spec.spec_id)
            except (json.JSONDecodeError, OSError):
                continue

        return ready

    def run_reconciliation_cycle(self) -> dict[str, Any]:
        """Run a single reconciliation cycle.

        Scans specs, processes pings, checks DAG readiness.

        :returns: Cycle summary with actions taken.
        """
        specs = self.scan_specs()
        pings = self.scan_pings()
        ping_actions = self.process_pings(pings)

        completed = {s.spec_id for s in specs if s.status == "DONE"}
        ready = self.specs_ready_for_assignment(specs, completed)

        event_count = len(pings) + len(ready)
        interval = self._reconciler.record_cycle(event_count)

        self._state.cycle_count += 1
        self._state.active_specs = {s.spec_id for s in specs if s.status in ("IN_PROGRESS", "REVIEW")}

        return {
            "cycle": self._state.cycle_count,
            "total_specs": len(specs),
            "active_specs": len(self._state.active_specs),
            "completed_specs": len(completed),
            "ready_for_assignment": ready,
            "pings_processed": len(ping_actions),
            "ping_actions": ping_actions,
            "next_interval": interval,
        }
