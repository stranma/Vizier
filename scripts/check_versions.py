#!/usr/bin/env python3
"""Cross-package version validation for monorepo projects.

Checks that all packages in the workspace have synchronized MAJOR.MINOR versions.
Patch versions are allowed to differ.

Usage:
    python scripts/check_versions.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def find_package_versions() -> dict[str, str]:
    """Find all packages and their versions from pyproject.toml files."""
    versions = {}

    # Check root
    root_toml = ROOT / "pyproject.toml"
    if root_toml.exists():
        version = extract_version(root_toml)
        if version:
            versions["root"] = version

    # Check libs/
    libs_dir = ROOT / "libs"
    if libs_dir.exists():
        for pkg_dir in sorted(libs_dir.iterdir()):
            toml = pkg_dir / "pyproject.toml"
            if toml.exists():
                version = extract_version(toml)
                if version:
                    versions[f"libs/{pkg_dir.name}"] = version

    # Check apps/
    apps_dir = ROOT / "apps"
    if apps_dir.exists():
        for pkg_dir in sorted(apps_dir.iterdir()):
            toml = pkg_dir / "pyproject.toml"
            if toml.exists():
                version = extract_version(toml)
                if version:
                    versions[f"apps/{pkg_dir.name}"] = version

    # Check plugins/
    plugins_dir = ROOT / "plugins"
    if plugins_dir.exists():
        for pkg_dir in sorted(plugins_dir.iterdir()):
            toml = pkg_dir / "pyproject.toml"
            if toml.exists():
                version = extract_version(toml)
                if version:
                    versions[f"plugins/{pkg_dir.name}"] = version

    return versions


def extract_version(toml_path: Path) -> str | None:
    """Extract version string from a pyproject.toml file."""
    content = toml_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    return match.group(1) if match else None


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse version string into (major, minor, patch) tuple."""
    parts = version_str.split(".")
    return (
        int(parts[0]) if len(parts) > 0 else 0,
        int(parts[1]) if len(parts) > 1 else 0,
        int(parts[2]) if len(parts) > 2 else 0,
    )


def check_version_sync(versions: dict[str, str]) -> list[str]:
    """Check that all MAJOR.MINOR versions match. Returns list of issues."""
    if len(versions) <= 1:
        return []

    issues = []
    major_minors: dict[str, list[str]] = {}

    for pkg, version in versions.items():
        major, minor, _patch = parse_version(version)
        key = f"{major}.{minor}"
        major_minors.setdefault(key, []).append(f"{pkg} ({version})")

    if len(major_minors) > 1:
        issues.append("MAJOR.MINOR version mismatch detected:")
        for mm, pkgs in sorted(major_minors.items()):
            for pkg in pkgs:
                issues.append(f"  {mm}.x: {pkg}")

    return issues


def main() -> None:
    print("Checking package versions...\n")

    versions = find_package_versions()

    if not versions:
        print("No packages found.")
        sys.exit(0)

    # Display versions
    max_name_len = max(len(name) for name in versions)
    for name, version in versions.items():
        print(f"  {name:<{max_name_len}}  {version}")

    # Check sync
    issues = check_version_sync(versions)
    if issues:
        print()
        for issue in issues:
            print(f"  [FAIL] {issue}")
        print("\nVersion check: FAILED")
        sys.exit(1)
    else:
        print("\n  [OK] All MAJOR.MINOR versions are synchronized")
        print("\nVersion check: PASSED")


if __name__ == "__main__":
    main()
