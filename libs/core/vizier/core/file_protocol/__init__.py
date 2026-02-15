"""File protocol: spec I/O, state management, criteria resolution."""

from vizier.core.file_protocol.criteria import resolve_criteria_references, snapshot_criteria
from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec, update_spec_status
from vizier.core.file_protocol.state_manager import StateManager

__all__ = [
    "StateManager",
    "create_spec",
    "list_specs",
    "read_spec",
    "resolve_criteria_references",
    "snapshot_criteria",
    "update_spec_status",
]
