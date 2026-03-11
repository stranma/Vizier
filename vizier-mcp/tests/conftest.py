"""Shared test fixtures for vizier-mcp v2 tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vizier_mcp.config import ServerConfig
from vizier_mcp.realm import RealmManager

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_vizier_root(tmp_path: Path) -> Path:
    """Create a temporary vizier root directory."""
    root = tmp_path / "vizier"
    root.mkdir()
    (root / "repos").mkdir()
    return root


@pytest.fixture
def config(tmp_vizier_root: Path) -> ServerConfig:
    """Create a ServerConfig pointing to a temp directory."""
    return ServerConfig(
        vizier_root=tmp_vizier_root,
        repos_dir=tmp_vizier_root / "repos",
    )


@pytest.fixture
def realm(tmp_vizier_root: Path) -> RealmManager:
    """Create a RealmManager with temp directory."""
    return RealmManager(tmp_vizier_root)
