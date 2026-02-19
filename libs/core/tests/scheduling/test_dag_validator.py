"""Tests for DAG validator (D52)."""

from __future__ import annotations

import pytest

from vizier.core.scheduling.dag_validator import (
    DagNode,
    DagValidationError,
    specs_ready_to_start,
    validate_dag,
)


class TestValidateDag:
    def test_linear_chain(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["b"]),
        ]
        order = validate_dag(nodes)
        assert order == ["a", "b", "c"]

    def test_diamond_dependency(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["a"]),
            DagNode(spec_id="d", depends_on=["b", "c"]),
        ]
        order = validate_dag(nodes)
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_independent_nodes(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b"),
            DagNode(spec_id="c"),
        ]
        order = validate_dag(nodes)
        assert len(order) == 3
        assert set(order) == {"a", "b", "c"}

    def test_single_node(self) -> None:
        nodes = [DagNode(spec_id="only")]
        order = validate_dag(nodes)
        assert order == ["only"]

    def test_empty_graph(self) -> None:
        order = validate_dag([])
        assert order == []

    def test_cycle_detection(self) -> None:
        nodes = [
            DagNode(spec_id="a", depends_on=["b"]),
            DagNode(spec_id="b", depends_on=["a"]),
        ]
        with pytest.raises(DagValidationError, match="Cycle detected"):
            validate_dag(nodes)

    def test_three_node_cycle(self) -> None:
        nodes = [
            DagNode(spec_id="a", depends_on=["c"]),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["b"]),
        ]
        with pytest.raises(DagValidationError, match="Cycle detected"):
            validate_dag(nodes)

    def test_self_reference(self) -> None:
        nodes = [DagNode(spec_id="a", depends_on=["a"])]
        with pytest.raises(DagValidationError, match="Self-reference"):
            validate_dag(nodes)

    def test_missing_dependency(self) -> None:
        nodes = [DagNode(spec_id="a", depends_on=["nonexistent"])]
        with pytest.raises(DagValidationError, match="Missing dependency"):
            validate_dag(nodes)

    def test_partial_cycle(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a", "c"]),
            DagNode(spec_id="c", depends_on=["b"]),
        ]
        with pytest.raises(DagValidationError, match="Cycle detected"):
            validate_dag(nodes)

    def test_complex_valid_dag(self) -> None:
        nodes = [
            DagNode(spec_id="models"),
            DagNode(spec_id="auth", depends_on=["models"]),
            DagNode(spec_id="api", depends_on=["models"]),
            DagNode(spec_id="middleware", depends_on=["auth", "api"]),
            DagNode(spec_id="tests", depends_on=["middleware"]),
        ]
        order = validate_dag(nodes)
        assert len(order) == 5
        assert order[0] == "models"
        assert order[-1] == "tests"


class TestSpecsReadyToStart:
    def test_all_independent(self) -> None:
        nodes = [DagNode(spec_id="a"), DagNode(spec_id="b"), DagNode(spec_id="c")]
        ready = specs_ready_to_start(nodes, completed=set())
        assert ready == ["a", "b", "c"]

    def test_chain_none_done(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["b"]),
        ]
        ready = specs_ready_to_start(nodes, completed=set())
        assert ready == ["a"]

    def test_chain_first_done(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["b"]),
        ]
        ready = specs_ready_to_start(nodes, completed={"a"})
        assert ready == ["b"]

    def test_diamond_partial(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["a"]),
            DagNode(spec_id="d", depends_on=["b", "c"]),
        ]
        ready = specs_ready_to_start(nodes, completed={"a", "b"})
        assert ready == ["c"]

    def test_diamond_both_done(self) -> None:
        nodes = [
            DagNode(spec_id="a"),
            DagNode(spec_id="b", depends_on=["a"]),
            DagNode(spec_id="c", depends_on=["a"]),
            DagNode(spec_id="d", depends_on=["b", "c"]),
        ]
        ready = specs_ready_to_start(nodes, completed={"a", "b", "c"})
        assert ready == ["d"]

    def test_all_completed(self) -> None:
        nodes = [DagNode(spec_id="a"), DagNode(spec_id="b", depends_on=["a"])]
        ready = specs_ready_to_start(nodes, completed={"a", "b"})
        assert ready == []
