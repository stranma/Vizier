"""Configuration models for server and project settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelTierConfig(BaseModel):
    """Maps tier names to concrete model identifiers."""

    opus: str = "anthropic/claude-opus-4-6"
    sonnet: str = "anthropic/claude-sonnet-4-5-20250929"
    haiku: str = "anthropic/claude-haiku-4-5-20251001"


class ProjectConfig(BaseModel):
    """Per-project configuration from .vizier/config.yaml."""

    plugin: str = "software"
    model_tiers: dict[str, str] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Server-wide configuration."""

    model_tiers: ModelTierConfig = Field(default_factory=ModelTierConfig)
    reports_dir: str = "reports"
    reconciliation_interval_seconds: int = Field(default=60, ge=1)
