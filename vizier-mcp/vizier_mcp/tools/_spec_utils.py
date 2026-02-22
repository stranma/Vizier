"""Shared utilities for spec-related tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from vizier_mcp.models.spec import SpecMetadata

if TYPE_CHECKING:
    from pathlib import Path


def parse_spec_metadata(spec_file: Path) -> SpecMetadata | None:
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
