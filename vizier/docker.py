"""Docker container management.

Creates, starts, stops, and destroys Docker containers for provinces.
Uses ``docker`` CLI via subprocess (no Docker SDK dependency). All subprocess
calls use list args to avoid shell injection.
"""
