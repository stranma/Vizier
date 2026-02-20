"""Worker self-verification tools (tests, lint, types).

These tools are called by Workers before transitioning to REVIEW (D68).
They delegate to the project's plugin to determine which commands to run
for each verification type, then execute them within the Sentinel-checked
command pipeline.
"""


async def verify_tests(project_id: str, spec_id: str) -> dict:
    """Run the plugin's test suite for the spec's modified artifacts.

    :param project_id: Project identifier.
    :param spec_id: Spec identifier (determines which files to test).
    :return: {"passed": bool, "output": str} with test results.
    """
    raise NotImplementedError


async def verify_lint(project_id: str, spec_id: str) -> dict:
    """Run the linter on the spec's modified files.

    :param project_id: Project identifier.
    :param spec_id: Spec identifier (determines which files to lint).
    :return: {"passed": bool, "output": str} with lint results.
    """
    raise NotImplementedError


async def verify_types(project_id: str, spec_id: str) -> dict:
    """Run the type checker on the spec's modified files.

    :param project_id: Project identifier.
    :param spec_id: Spec identifier (determines which files to check).
    :return: {"passed": bool, "output": str} with type check results.
    """
    raise NotImplementedError
