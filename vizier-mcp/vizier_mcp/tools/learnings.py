"""Failure learnings tools for retry context injection.

Provides learnings_extract, learnings_list, and learnings_inject tools
for extracting failure context from rejected/stuck specs and injecting
it into retry attempts. Storage is append-only JSONL at
{projects_dir}/{project_id}/.vizier/learnings/learnings.jsonl.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.learnings import Learning, LearningCategory
from vizier_mcp.tools._spec_utils import parse_spec_metadata

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig


def _learnings_dir(config: ServerConfig, project_id: str) -> Path:
    """Return the learnings directory for a project."""
    assert config.projects_dir is not None
    return config.projects_dir / project_id / ".vizier" / "learnings"


def _learnings_file(config: ServerConfig, project_id: str) -> Path:
    """Return the JSONL learnings file for a project."""
    return _learnings_dir(config, project_id) / "learnings.jsonl"


def _read_existing_learnings(config: ServerConfig, project_id: str) -> list[Learning]:
    """Read all learnings from the JSONL file."""
    lfile = _learnings_file(config, project_id)
    if not lfile.exists():
        return []
    learnings: list[Learning] = []
    for line in lfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            learnings.append(Learning.model_validate_json(line))
        except Exception:
            continue
    return learnings


def _append_learning(config: ServerConfig, learning: Learning) -> None:
    """Append a learning to the JSONL file, creating dirs as needed."""
    ldir = _learnings_dir(config, learning.project_id)
    ldir.mkdir(parents=True, exist_ok=True)
    lfile = ldir / "learnings.jsonl"
    with open(lfile, "a", encoding="utf-8") as f:
        f.write(learning.model_dump_json() + "\n")


def _read_feedback_files(spec_dir: Path) -> list[dict[str, Any]]:
    """Read all feedback JSON files from a spec's feedback directory."""
    fb_dir = spec_dir / "feedback"
    if not fb_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    for fb_file in sorted(fb_dir.iterdir()):
        if not fb_file.is_file() or fb_file.suffix != ".json":
            continue
        try:
            results.append(json.loads(fb_file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _read_ping_files(spec_dir: Path) -> list[dict[str, Any]]:
    """Read all ping JSON files from a spec's pings directory."""
    pings_dir = spec_dir / "pings"
    if not pings_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    for ping_file in sorted(pings_dir.iterdir()):
        if not ping_file.is_file() or ping_file.suffix != ".json":
            continue
        try:
            results.append(json.loads(ping_file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return results


_CATEGORY_PATTERNS: list[tuple[str, LearningCategory]] = [
    (r"(?i)test.*fail|assert.*error|pytest|unittest", LearningCategory.test_failure),
    (r"(?i)lint|ruff|flake8|pylint|style|format", LearningCategory.lint_failure),
    (r"(?i)type.*error|pyright|mypy|type.?check", LearningCategory.type_error),
    (r"(?i)sentinel.*denied|sentinel.*block|not.?allowed|permission", LearningCategory.sentinel_denied),
    (r"(?i)timeout|timed?.?out|deadline|too.?long", LearningCategory.timeout),
    (r"(?i)impossible|cannot|defective|contradictory", LearningCategory.impossible),
]


def _categorize_feedback(text: str) -> str:
    """Categorize feedback text using keyword heuristics.

    :param text: Combined feedback and ping text.
    :return: Category string matching a LearningCategory value.
    """
    for pattern, category in _CATEGORY_PATTERNS:
        if re.search(pattern, text):
            return category.value
    return LearningCategory.spec_ambiguity.value


def _extract_keywords(text: str) -> list[str]:
    """Extract keywords (>3 chars, unique, lowercase) from text.

    :param text: Source text to extract keywords from.
    :return: List of unique lowercase keywords longer than 3 characters.
    """
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text)
    seen: set[str] = set()
    result: list[str] = []
    for w in words:
        lower = w.lower()
        if len(lower) > 3 and lower not in seen:
            seen.add(lower)
            result.append(lower)
    return result


def learnings_extract(
    config: ServerConfig,
    project_id: str,
    spec_id: str | None = None,
) -> dict[str, Any]:
    """Extract failure learnings from REJECTED and STUCK specs.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Optional specific spec to extract from.
    :return: {"extracted": int, "learnings": list[dict]} on success, {"error": str} on failure.
    """
    assert config.projects_dir is not None
    specs_dir = config.projects_dir / project_id / "specs"

    if not specs_dir.exists():
        return {"extracted": 0, "learnings": []}

    existing = _read_existing_learnings(config, project_id)
    existing_source_ids = {le.source_spec_id for le in existing}

    spec_dirs: list[Path] = []
    if spec_id:
        target = specs_dir / spec_id
        if not target.exists():
            return {"error": f"spec {spec_id} not found"}
        spec_dirs = [target]
    else:
        spec_dirs = [d for d in specs_dir.iterdir() if d.is_dir()]

    new_learnings: list[Learning] = []
    for sdir in spec_dirs:
        sid = sdir.name
        if sid in existing_source_ids:
            continue

        spec_file = sdir / "spec.md"
        if not spec_file.exists():
            continue

        meta = parse_spec_metadata(spec_file)
        if meta is None:
            continue

        if meta.status.value not in ("REJECTED", "STUCK"):
            continue

        feedbacks = _read_feedback_files(sdir)
        pings = _read_ping_files(sdir)

        combined_text_parts: list[str] = []
        for fb in feedbacks:
            combined_text_parts.append(fb.get("feedback", ""))
        for ping in pings:
            combined_text_parts.append(ping.get("message", ""))
        combined_text = " ".join(combined_text_parts)

        if not combined_text.strip():
            summary = f"Spec {sid} reached {meta.status.value} state"
            combined_text = summary
        else:
            summary = combined_text[:200].strip()

        category = _categorize_feedback(combined_text)
        keywords = _extract_keywords(combined_text)

        learning = Learning(
            learning_id=uuid.uuid4().hex,
            source_spec_id=sid,
            project_id=project_id,
            category=category,
            summary=summary,
            detail=combined_text,
            keywords=keywords,
        )
        _append_learning(config, learning)
        new_learnings.append(learning)

    return {
        "extracted": len(new_learnings),
        "learnings": [le.model_dump(mode="json") for le in new_learnings],
    }


def learnings_list(
    config: ServerConfig,
    project_id: str,
    spec_id: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List failure learnings with optional filters.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Filter by source spec identifier.
    :param category: Filter by learning category.
    :param limit: Maximum number of learnings to return.
    :return: {"learnings": list[dict], "total": int} on success, {"error": str} on failure.
    """
    assert config.projects_dir is not None

    if category is not None:
        valid_categories = {c.value for c in LearningCategory}
        if category not in valid_categories:
            return {"error": f"invalid category: {category}. Valid: {sorted(valid_categories)}"}

    learnings = _read_existing_learnings(config, project_id)

    if spec_id is not None:
        learnings = [le for le in learnings if le.source_spec_id == spec_id]

    if category is not None:
        learnings = [le for le in learnings if le.category == category]

    learnings.sort(key=lambda le: le.created_at, reverse=True)
    total = len(learnings)
    learnings = learnings[:limit]

    return {
        "learnings": [le.model_dump(mode="json") for le in learnings],
        "total": total,
    }


def learnings_inject(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
) -> dict[str, Any]:
    """Match and format failure learnings for injection into a spec's Worker context.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Target spec to inject learnings into.
    :return: {"matches": list[dict], "context_text": str} on success, {"error": str} on failure.
    """
    assert config.projects_dir is not None
    specs_dir = config.projects_dir / project_id / "specs"
    spec_dir = specs_dir / spec_id

    if not spec_dir.exists():
        return {"error": f"spec {spec_id} not found"}

    spec_file = spec_dir / "spec.md"
    if not spec_file.exists():
        return {"error": f"spec {spec_id} has no spec.md"}

    meta = parse_spec_metadata(spec_file)
    target_keywords: set[str] = set()
    if meta:
        title_keywords = _extract_keywords(meta.title)
        target_keywords.update(title_keywords)

    all_learnings = _read_existing_learnings(config, project_id)
    if not all_learnings:
        return {"matches": [], "context_text": ""}

    matches: list[dict[str, Any]] = []

    for le in all_learnings:
        if le.source_spec_id == spec_id:
            matches.append(
                {
                    "learning": le.model_dump(mode="json"),
                    "match_reason": "same spec (prior attempt)",
                }
            )
            continue

        if target_keywords:
            learning_keywords = set(le.keywords)
            overlap = target_keywords & learning_keywords
            if overlap:
                matches.append(
                    {
                        "learning": le.model_dump(mode="json"),
                        "match_reason": f"keyword overlap: {', '.join(sorted(overlap))}",
                    }
                )

    matches.sort(key=lambda m: m["learning"]["created_at"], reverse=True)
    matches = matches[:10]

    if not matches:
        return {"matches": [], "context_text": ""}

    lines: list[str] = ["## Failure Learnings (auto-injected)", ""]
    for i, m in enumerate(matches, 1):
        le_data = m["learning"]
        lines.append(f"### {i}. [{le_data['category']}] from {le_data['source_spec_id']}")
        lines.append(f"**Match:** {m['match_reason']}")
        lines.append(f"**Summary:** {le_data['summary']}")
        if le_data.get("detail") and le_data["detail"] != le_data["summary"]:
            lines.append(f"**Detail:** {le_data['detail'][:500]}")
        lines.append("")

    context_text = "\n".join(lines)

    return {
        "matches": matches,
        "context_text": context_text,
    }
