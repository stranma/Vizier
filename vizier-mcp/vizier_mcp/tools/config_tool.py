"""Project configuration tool (replaces plugin framework in v1)."""


async def project_get_config(project_id: str) -> dict:
    """Get project configuration including plugin type and settings.

    Returns the project's type (software, documents), language, framework,
    test commands, lint commands, and any custom settings. Replaces the v1
    need for plugin_get_write_set, plugin_get_evidence_requirements,
    plugin_get_system_prompt, plugin_get_criteria, and
    plugin_get_decomposition_guide.

    :param project_id: Project identifier.
    :return: {"type": str, "settings": dict} with project config.
    """
    raise NotImplementedError
