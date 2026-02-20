"""E2E validation script: runs a real agent cycle against the Anthropic API.

Requires ANTHROPIC_API_KEY env var. NOT part of CI -- manual validation only.

Usage:
    ANTHROPIC_API_KEY=sk-... uv run python scripts/run_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def _setup_project(root: Path) -> Path:
    """Create minimal Vizier project structure with a READY spec."""
    (root / "workspaces" / "e2e_test" / ".vizier" / "specs" / "001").mkdir(parents=True)
    (root / "reports").mkdir(parents=True)
    (root / "ea").mkdir(parents=True)
    (root / "security").mkdir(parents=True)
    (root / "logs").mkdir(parents=True)

    project_dir = root / "workspaces" / "e2e_test"

    spec_dir = project_dir / ".vizier" / "specs" / "001"
    state = {
        "status": "READY",
        "created_at": "2026-01-01T00:00:00Z",
        "retries": 0,
    }
    (spec_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    spec_content = """---
id: "001"
title: "Add hello function"
status: READY
priority: MEDIUM
plugin: software
---

# Task

Create a file `main.py` in the project root with a function `hello()` that returns
the string "Hello from Vizier!".

## Acceptance Criteria

- `main.py` exists
- Contains a function `hello()` that returns "Hello from Vizier!"
"""
    (spec_dir / "spec.md").write_text(spec_content, encoding="utf-8")
    return project_dir


def _create_config(root: Path) -> None:
    """Write minimal config and registry YAML files."""
    import yaml

    config = {
        "vizier_root": str(root),
        "health_check_port": 19876,
        "reconciliation_interval": 30,
        "max_concurrent_agents": 2,
        "autonomy": {"stage": 1},
    }
    (root / "config.yaml").write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")

    registry = {
        "projects": [
            {
                "name": "e2e_test",
                "active": True,
                "plugin": "software",
                "repo_url": "",
                "local_path": str(root / "workspaces" / "e2e_test"),
            }
        ]
    }
    (root / "projects.yaml").write_text(yaml.dump(registry, default_flow_style=False), encoding="utf-8")


def main() -> None:
    """Run a single reconciliation cycle with real Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable required")
        print("Usage: ANTHROPIC_API_KEY=sk-... uv run python scripts/run_e2e.py")
        sys.exit(1)

    print("=" * 60)
    print("Vizier E2E Validation")
    print("=" * 60)

    with tempfile.TemporaryDirectory(prefix="vizier_e2e_") as tmpdir:
        root = Path(tmpdir)
        print(f"\nTemp root: {root}")

        print("\n1. Setting up project structure...")
        project_dir = _setup_project(root)
        _create_config(root)
        print(f"   Project dir: {project_dir}")
        print("   Spec 001: READY")

        print("\n2. Creating daemon...")
        from vizier.daemon.config import DaemonConfig, ProjectEntry, ProjectRegistry
        from vizier.daemon.process import VizierDaemon

        class _EnvSecretStore:
            def get(self, key: str) -> str | None:
                return os.environ.get(key)

        config = DaemonConfig(vizier_root=str(root), health_check_port=19876)
        registry = ProjectRegistry(
            projects=[
                ProjectEntry(
                    name="e2e_test",
                    active=True,
                    plugin="software",
                    local_path=str(project_dir),
                )
            ]
        )
        store = _EnvSecretStore()

        daemon = VizierDaemon(config, registry, store)
        daemon.setup()
        print("   Daemon setup complete")

        print("\n3. Running single reconciliation cycle...")
        start_time = time.monotonic()
        results = asyncio.run(daemon.run_once())
        elapsed = time.monotonic() - start_time

        print(f"\n4. Results (took {elapsed:.1f}s):")
        print(json.dumps(results, indent=2, default=str))

        print("\n5. Post-cycle inspection:")
        spec_state_path = project_dir / ".vizier" / "specs" / "001" / "state.json"
        if spec_state_path.exists():
            state = json.loads(spec_state_path.read_text(encoding="utf-8"))
            print(f"   Spec 001 status: {state.get('status', 'UNKNOWN')}")
        else:
            print("   Spec 001 state.json not found")

        main_py = project_dir / "main.py"
        if main_py.exists():
            print("   main.py created: YES")
            print(f"   Content:\n{main_py.read_text(encoding='utf-8')}")
        else:
            print("   main.py created: NO")

        trace_dir = project_dir / ".vizier" / "specs" / "001"
        trace_files = list(trace_dir.glob("*.jsonl"))
        print(f"   Trace files: {[f.name for f in trace_files]}")

    print("\n" + "=" * 60)
    print("E2E validation complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
