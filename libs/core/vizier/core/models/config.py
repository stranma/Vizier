"""Configuration models for server and project settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelTierConfig(BaseModel):
    """Maps tier names to concrete model identifiers."""

    opus: str = "claude-opus-4-6"
    sonnet: str = "claude-sonnet-4-6"
    haiku: str = "claude-haiku-4-5-20251001"


class ProjectConfig(BaseModel):
    """Per-project configuration from .vizier/config.yaml."""

    plugin: str = "software"
    model_tiers: dict[str, str] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Server-wide configuration."""

    model_tiers: ModelTierConfig = Field(default_factory=ModelTierConfig)
    reports_dir: str = "reports"
    reconciliation_interval_seconds: int = Field(default=15, ge=1)
