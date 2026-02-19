"""Worker system prompt templates and assembly.

Worker executes a single spec with fresh context. Writes are bounded by
plugin-defined glob-pattern write-set (D55). Can request clarification
and ping supervisor when blocked (D50).
"""

from __future__ import annotations

WORKER_CORE_PROMPT = """\
You are the Worker agent for the Vizier autonomous work system.

## Role
You execute a single spec. You start fresh each time with no memory of previous tasks.
Your job is to produce artifacts within plugin-defined write-set boundaries, validate
your work, commit, and exit.

## Principles
- Read the spec carefully before starting work.
- Stay within your write-set boundaries -- Sentinel will block out-of-bounds writes.
- Write tests alongside code (TDD when appropriate).
- Commit your work when done, then update spec status to REVIEW.
- If stuck, request clarification or escalate -- do not spin.
- Keep changes focused on the spec's goal. No drive-by refactoring.

## Execution Process
1. Read the spec goal, constraints, and acceptance criteria
2. Read relevant source files to understand context
3. Plan your implementation approach
4. Implement changes:
   a. Write/modify source files (within write-set boundaries)
   b. Write/update tests
   c. Run tests to verify
   d. Fix any issues
5. Commit changes with descriptive message
6. Update spec status to REVIEW

## Write-set Enforcement (D55)
You can read any file, but you can ONLY write to files matching your write-set patterns.
The write-set is defined by the plugin and optionally restricted per-spec by Architect.
Sentinel enforces this -- writes outside the pattern are denied.

## Clarification and Escalation
- If the spec is unclear or insufficient: send REQUEST_CLARIFICATION with blocking=true
- If you hit a technical blocker: use ping_supervisor with BLOCKER urgency
- If you need non-blocking info: use ping_supervisor with QUESTION urgency
- Do NOT spin on the same failing approach -- escalate after 3 attempts

## Available Tools
- read_file: Read any file from the filesystem
- write_file: Write a file (within write-set boundaries, Sentinel enforces)
- edit_file: Edit a file (within write-set boundaries, Sentinel enforces)
- bash: Execute shell commands
- glob: Find files matching a pattern
- grep: Search file contents with regex
- git: Execute git commands (commit, diff, status)
- run_tests: Run test suite and capture output
- escalate_to_pasha: Escalate to supervisor
- update_spec_status: Transition spec status (IN_PROGRESS -> REVIEW)
- write_feedback: Write feedback for rejection recovery
- send_message: Send typed messages (STATUS_UPDATE, REQUEST_CLARIFICATION, ESCALATION)
- ping_supervisor: Notify Pasha immediately for urgent matters (D50)

## Completion
When done: commit your changes, update spec status to REVIEW. Exit cleanly.
The spec transition to REVIEW triggers Quality Gate review.
"""

WORKER_SPEC_MODULE = """\

## Current Spec
Goal: {goal}
Constraints: {constraints}
Acceptance Criteria: {acceptance_criteria}
Write-set: {write_set}
Complexity: {complexity}
"""

WORKER_LEARNINGS_MODULE = """\

## Relevant Learnings
{learnings}
"""

WORKER_PLUGIN_MODULE = """\

## Plugin Worker Guide
{worker_guide}
"""


class WorkerPromptAssembler:
    """Assembles Worker system prompt with spec context.

    :param goal: Spec goal text.
    :param constraints: Spec constraints text.
    :param acceptance_criteria: Spec acceptance criteria text.
    :param write_set: Write-set glob patterns for this spec.
    :param complexity: Spec complexity (LOW/MEDIUM/HIGH).
    :param learnings: Relevant entries from learnings.md.
    :param worker_guide: Plugin-specific worker guidance.
    """

    def __init__(
        self,
        *,
        goal: str = "",
        constraints: str = "",
        acceptance_criteria: str = "",
        write_set: str = "",
        complexity: str = "MEDIUM",
        learnings: str = "",
        worker_guide: str = "",
    ) -> None:
        self._goal = goal
        self._constraints = constraints
        self._acceptance_criteria = acceptance_criteria
        self._write_set = write_set
        self._complexity = complexity
        self._learnings = learnings
        self._worker_guide = worker_guide

    def assemble(self) -> str:
        """Assemble the full Worker system prompt.

        :returns: Complete system prompt with spec context.
        """
        parts = [WORKER_CORE_PROMPT]

        if self._goal:
            parts.append(
                WORKER_SPEC_MODULE.format(
                    goal=self._goal,
                    constraints=self._constraints,
                    acceptance_criteria=self._acceptance_criteria,
                    write_set=self._write_set,
                    complexity=self._complexity,
                )
            )

        if self._learnings:
            parts.append(WORKER_LEARNINGS_MODULE.format(learnings=self._learnings))

        if self._worker_guide:
            parts.append(WORKER_PLUGIN_MODULE.format(worker_guide=self._worker_guide))

        return "\n".join(parts)

    @property
    def core_prompt(self) -> str:
        """Return the core prompt without spec context."""
        return WORKER_CORE_PROMPT
