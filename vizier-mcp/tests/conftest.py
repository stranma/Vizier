"""Shared test fixtures for vizier-mcp tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vizier_mcp.config import ServerConfig

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_vizier_root(tmp_path: Path) -> Path:
    """Create a temporary vizier root directory."""
    root = tmp_path / "vizier"
    root.mkdir()
    (root / "projects").mkdir()
    return root


@pytest.fixture
def config(tmp_vizier_root: Path) -> ServerConfig:
    """Create a ServerConfig pointing to a temp directory."""
    return ServerConfig(
        vizier_root=tmp_vizier_root,
        projects_dir=tmp_vizier_root / "projects",
    )


@pytest.fixture
def project_dir(config: ServerConfig) -> Path:
    """Create a test project directory."""
    assert config.projects_dir is not None
    proj = config.projects_dir / "test-project"
    proj.mkdir(parents=True)
    (proj / "specs").mkdir()
    return proj
