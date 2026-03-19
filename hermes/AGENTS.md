# Vizier Project Context

## Architecture

Vizier is a secure software-organization layer built on Hermes.
The Vizier MCP server (`vizier-mcp/`) provides domain tools via FastMCP.

## Available MCP Tools

The `vizier` MCP server provides these tools (prefixed as `mcp_vizier_*`):

- `realm_list_projects` -- list all projects in the realm
- `realm_create_project` -- create a new project
- `realm_get_project` -- get project details and status
- `container_start` -- start a project's devcontainer
- `container_stop` -- stop a project's devcontainer
- `container_status` -- check container state

## Conventions

- Use plain ASCII in all output (no special Unicode characters)
- Log structured data via the MCP server's built-in logging
- All secrets are in environment variables, never in config files
