"""Golden Trace analyzer (D57): reads trace.jsonl files for behavioral patterns.

Analyzes per-spec trace files to identify:
- Tool call frequency and error rates
- Repeated identical tool calls (spinning)
- Escalation chains
- Budget usage patterns
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class TraceStats:
    """Aggregated statistics from trace analysis.

    :param total_tool_calls: Total number of tool calls across all traces.
    :param error_count: Number of tool calls that returned errors.
    :param tool_frequency: Count of each tool name used.
    :param repeated_calls: Number of identical consecutive tool calls detected.
    :param specs_analyzed: Number of spec traces analyzed.
    :param escalation_count: Number of escalation events found.
    """

    total_tool_calls: int = 0
    error_count: int = 0
    tool_frequency: dict[str, int] = field(default_factory=dict)
    repeated_calls: int = 0
    specs_analyzed: int = 0
    escalation_count: int = 0


def analyze_trace_file(trace_path: str) -> TraceStats:
    """Analyze a single trace.jsonl file.

    :param trace_path: Path to the trace.jsonl file.
    :returns: TraceStats for this trace file.
    """
    stats = TraceStats(specs_analyzed=1)

    if not os.path.isfile(trace_path):
        return stats

    prev_call: str | None = None
    try:
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                tool_name = entry.get("tool_name", "")
                if tool_name:
                    stats.total_tool_calls += 1
                    stats.tool_frequency[tool_name] = stats.tool_frequency.get(tool_name, 0) + 1

                    call_sig = f"{tool_name}:{json.dumps(entry.get('tool_input', {}), sort_keys=True)}"
                    if call_sig == prev_call:
                        stats.repeated_calls += 1
                    prev_call = call_sig

                sentinel_decision = entry.get("sentinel_decision", "ALLOW")
                if sentinel_decision == "DENY":
                    stats.error_count += 1

                result = entry.get("tool_result", {})
                if isinstance(result, dict) and "error" in result:
                    stats.error_count += 1

                if tool_name in ("escalate_to_pasha", "escalate_to_ea"):
                    stats.escalation_count += 1

    except OSError:
        pass

    return stats


def analyze_project_traces(project_root: str) -> TraceStats:
    """Analyze all trace.jsonl files in a project.

    :param project_root: Project root directory.
    :returns: Aggregated TraceStats across all specs.
    """
    aggregate = TraceStats()
    specs_dir = os.path.join(project_root, ".vizier", "specs")

    if not os.path.isdir(specs_dir):
        return aggregate

    for spec_id in sorted(os.listdir(specs_dir)):
        trace_path = os.path.join(specs_dir, spec_id, "trace.jsonl")
        if not os.path.isfile(trace_path):
            continue

        spec_stats = analyze_trace_file(trace_path)
        aggregate.specs_analyzed += spec_stats.specs_analyzed
        aggregate.total_tool_calls += spec_stats.total_tool_calls
        aggregate.error_count += spec_stats.error_count
        aggregate.repeated_calls += spec_stats.repeated_calls
        aggregate.escalation_count += spec_stats.escalation_count
        for tool, count in spec_stats.tool_frequency.items():
            aggregate.tool_frequency[tool] = aggregate.tool_frequency.get(tool, 0) + count

    return aggregate


def format_trace_summary(stats: TraceStats) -> str:
    """Format trace stats as a human-readable summary.

    :param stats: TraceStats to format.
    :returns: Formatted summary string.
    """
    lines = [
        f"Specs analyzed: {stats.specs_analyzed}",
        f"Total tool calls: {stats.total_tool_calls}",
        f"Errors: {stats.error_count}",
        f"Repeated calls (spinning): {stats.repeated_calls}",
        f"Escalations: {stats.escalation_count}",
    ]

    if stats.total_tool_calls > 0:
        error_rate = stats.error_count / stats.total_tool_calls * 100
        lines.append(f"Error rate: {error_rate:.1f}%")

    if stats.tool_frequency:
        lines.append("Tool usage:")
        for tool, count in sorted(stats.tool_frequency.items(), key=lambda x: -x[1]):
            lines.append(f"  {tool}: {count}")

    return "\n".join(lines)
