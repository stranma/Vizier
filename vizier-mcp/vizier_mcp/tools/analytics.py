"""Spec analytics MCP tool (D82, Phase 9).

Returns per-project metrics: throughput, timing, quality, and sentinel stats.
Reads from spec filesystem (YAML frontmatter), feedback directories,
and structured logs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml

from vizier_mcp.models.spec import SpecMetadata, SpecStatus

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig
    from vizier_mcp.logging_structured import StructuredLogger


def _parse_spec_metadata(spec_file: Path) -> SpecMetadata | None:
    """Parse spec.md frontmatter into SpecMetadata, returning None on error."""
    try:
        content = spec_file.read_text()
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return None
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx == -1:
            return None
        frontmatter = "\n".join(lines[1:end_idx])
        meta_dict = yaml.safe_load(frontmatter) or {}
        return SpecMetadata(**meta_dict)
    except Exception:
        return None


def _count_feedback_files(spec_dir: Path) -> dict[str, int]:
    """Count feedback files by verdict type."""
    fb_dir = spec_dir / "feedback"
    counts: dict[str, int] = {"accept": 0, "reject": 0}
    if not fb_dir.exists():
        return counts
    for fb_file in fb_dir.iterdir():
        if not fb_file.is_file() or fb_file.suffix != ".json":
            continue
        try:
            data = json.loads(fb_file.read_text())
            verdict = data.get("verdict", "").lower()
            if verdict in counts:
                counts[verdict] += 1
        except (json.JSONDecodeError, OSError):
            continue
    return counts


def spec_analytics(
    config: ServerConfig,
    slog: StructuredLogger,
    project_id: str,
) -> dict[str, Any]:
    """Return per-project spec analytics.

    :param config: Server configuration.
    :param slog: Structured logger for sentinel stats.
    :param project_id: Project identifier.
    :return: Analytics dict with throughput, timing, quality, sentinel sections.
    """
    assert config.projects_dir is not None
    specs_dir = config.projects_dir / project_id / "specs"

    all_meta: list[SpecMetadata] = []
    all_feedback: dict[str, dict[str, int]] = {}

    if specs_dir.exists():
        for spec_dir in specs_dir.iterdir():
            if not spec_dir.is_dir():
                continue
            spec_file = spec_dir / "spec.md"
            if not spec_file.exists():
                continue
            meta = _parse_spec_metadata(spec_file)
            if meta is None:
                continue
            all_meta.append(meta)
            all_feedback[meta.spec_id] = _count_feedback_files(spec_dir)

    throughput = _compute_throughput(all_meta)
    timing = _compute_timing(all_meta)
    quality = _compute_quality(all_meta, all_feedback)
    sentinel = _compute_sentinel_stats(slog, project_id)

    return {
        "project_id": project_id,
        "total_specs": len(all_meta),
        "throughput": throughput,
        "timing": timing,
        "quality": quality,
        "sentinel": sentinel,
    }


def _compute_throughput(specs: list[SpecMetadata]) -> dict[str, Any]:
    """Compute throughput metrics."""
    completed = sum(1 for s in specs if s.status == SpecStatus.DONE)
    stuck = sum(1 for s in specs if s.status == SpecStatus.STUCK)
    total = len(specs)
    success_rate = round(completed / total, 2) if total > 0 else 0.0

    return {
        "completed": completed,
        "stuck": stuck,
        "in_progress": sum(1 for s in specs if s.status == SpecStatus.IN_PROGRESS),
        "total": total,
        "success_rate": success_rate,
    }


def _compute_timing(specs: list[SpecMetadata]) -> dict[str, Any]:
    """Compute timing metrics from spec metadata."""
    done_specs = [s for s in specs if s.status == SpecStatus.DONE]

    durations: list[float] = []
    for s in done_specs:
        duration_mins = (s.updated_at - s.created_at).total_seconds() / 60
        durations.append(duration_mins)

    review_durations: list[float] = []
    for s in specs:
        if s.status == SpecStatus.REVIEW and s.claimed_at:
            review_mins = (datetime.now(UTC) - s.claimed_at).total_seconds() / 60
            review_durations.append(review_mins)

    slowest: dict[str, Any] | None = None
    if durations:
        max_dur = max(durations)
        slowest_spec = done_specs[durations.index(max_dur)]
        slowest = {
            "spec_id": slowest_spec.spec_id,
            "duration_minutes": round(max_dur, 1),
        }

    return {
        "avg_time_to_done_minutes": round(sum(durations) / len(durations), 1) if durations else 0.0,
        "avg_time_in_review_minutes": round(sum(review_durations) / len(review_durations), 1)
        if review_durations
        else 0.0,
        "slowest_spec": slowest,
    }


def _compute_quality(specs: list[SpecMetadata], feedback: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Compute quality metrics from spec metadata and feedback."""
    total_rejections = sum(fb.get("reject", 0) for fb in feedback.values())
    total_retries = sum(s.retry_count for s in specs)
    specs_with_retries = sum(1 for s in specs if s.retry_count > 0)
    avg_retries = round(total_retries / len(specs), 2) if specs else 0.0

    return {
        "rejection_count": total_rejections,
        "total_retries": total_retries,
        "specs_with_retries": specs_with_retries,
        "avg_retries": avg_retries,
    }


def _compute_sentinel_stats(slog: StructuredLogger, project_id: str) -> dict[str, Any]:
    """Compute sentinel stats from structured logs."""
    all_tool_calls = slog.read_entries(event="tool_call", since_minutes=1440, limit=10000)
    sentinel_tools = {"sentinel_check_write", "run_command_checked", "web_fetch_checked"}
    sentinel_calls = [e for e in all_tool_calls["entries"] if e.get("data", {}).get("tool") in sentinel_tools]

    denials = slog.read_entries(event="sentinel_decision", since_minutes=1440, limit=10000)

    return {
        "total_checks": len(sentinel_calls),
        "denials": denials["total_matched"],
    }
