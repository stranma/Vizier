"""DAG validator for spec dependency graphs (D52).

Validates that PROPOSE_PLAN dependency graphs are acyclic, all referenced
IDs exist, and there are no self-references. Uses topological sort (Kahn's
algorithm) for cycle detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class DagValidationError(Exception):
    """Raised when a dependency graph is invalid."""


@dataclass
class DagNode:
    """A node in the dependency graph."""

    spec_id: str
    depends_on: list[str] = field(default_factory=list)


def validate_dag(nodes: list[DagNode]) -> list[str]:
    """Validate a dependency graph and return topological order.

    :param nodes: List of DagNode with spec_id and depends_on lists.
    :returns: List of spec IDs in topological order (dependencies first).
    :raises DagValidationError: If the graph has cycles, missing IDs, or self-references.
    """
    known_ids = {n.spec_id for n in nodes}

    for node in nodes:
        if node.spec_id in node.depends_on:
            raise DagValidationError(f"Self-reference: {node.spec_id} depends on itself")
        for dep in node.depends_on:
            if dep not in known_ids:
                raise DagValidationError(f"Missing dependency: {node.spec_id} depends on unknown '{dep}'")

    adjacency: dict[str, list[str]] = {n.spec_id: [] for n in nodes}
    in_degree: dict[str, int] = {n.spec_id: 0 for n in nodes}

    for node in nodes:
        for dep in node.depends_on:
            adjacency[dep].append(node.spec_id)
            in_degree[node.spec_id] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        queue.sort()
        current = queue.pop(0)
        order.append(current)
        for neighbor in adjacency[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        visited = set(order)
        cycle_nodes = [n.spec_id for n in nodes if n.spec_id not in visited]
        raise DagValidationError(f"Cycle detected involving: {cycle_nodes}")

    return order


def specs_ready_to_start(
    nodes: list[DagNode],
    completed: set[str],
) -> list[str]:
    """Return spec IDs whose dependencies are all completed.

    :param nodes: Full dependency graph.
    :param completed: Set of spec IDs that are DONE.
    :returns: List of spec IDs ready to start (all depends_on in completed).
    """
    ready = []
    for node in nodes:
        if node.spec_id in completed:
            continue
        if all(dep in completed for dep in node.depends_on):
            ready.append(node.spec_id)
    return sorted(ready)
