"""Strict model-directed planning for the small Step 6 read-only allowlist."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .contracts import STATE_TOOL_NAMES, StateNeedsPlan, ToolResult
from .investigation import InvestigationPlanError, validate_steps


MAX_STATE_TOOLS = len(STATE_TOOL_NAMES)
MAX_PRIOR_CONTEXT_CHARS = 8_000


class StatePlanError(ValueError):
    """Raised when provider output is not exactly the safe planning schema."""


def validate_state_plan(raw: str) -> StateNeedsPlan:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise StatePlanError("state plan is not valid JSON") from error
    if not isinstance(value, dict) or not set(value) <= {"tools", "steps"} or "tools" not in value:
        raise StatePlanError("state plan must contain tools and optional steps only")
    tools = value["tools"]
    if not isinstance(tools, list) or not all(isinstance(item, str) for item in tools):
        raise StatePlanError("state plan tools must be a list of names")
    if len(tools) > MAX_STATE_TOOLS:
        raise StatePlanError("state plan selects too many tools")
    if len(set(tools)) != len(tools):
        raise StatePlanError("state plan contains duplicate tools")
    unknown = [item for item in tools if item not in STATE_TOOL_NAMES]
    if unknown:
        raise StatePlanError("state plan contains unknown tool(s): " + ",".join(unknown))
    try:
        steps = validate_steps(value.get("steps", []))
    except InvestigationPlanError as error:
        raise StatePlanError(str(error)) from error
    return StateNeedsPlan(tuple(tools), tuple(step.to_data() for step in steps))


def planning_context(
    request_text: str,
    history: Sequence[tuple[str, str]],
    prior_results: Sequence[ToolResult],
) -> str:
    """Serialize bounded conversational inputs as data for the model planner."""
    data: Mapping[str, object] = {
        "request": request_text,
        "recent_exchanges": [
            {"player": user, "jimbo": assistant} for user, assistant in history
        ],
        "most_recent_observations": [_compact_result(result) for result in prior_results],
    }
    encoded = json.dumps(data, ensure_ascii=False)
    if len(encoded) > MAX_PRIOR_CONTEXT_CHARS:
        data["most_recent_observations"] = [
            {"status": result.status.value, "summary": result.summary,
             "warnings": list(result.warnings)} for result in prior_results
        ]
        encoded = json.dumps(data, ensure_ascii=False)
    return encoded[:MAX_PRIOR_CONTEXT_CHARS]


def _compact_result(result: ToolResult) -> dict[str, object]:
    data = result.to_data()
    values = data.get("values", {})
    if isinstance(values, dict) and isinstance(values.get("results"), list):
        compact_rows = []
        for row in values["results"][:16]:
            if isinstance(row, dict):
                compact_rows.append({key: row[key] for key in (
                    "id", "name", "surface", "network_id", "unit_number",
                    "position", "location", "location_kind", "item", "member", "count",
                ) if key in row})
        values = {key: value for key, value in values.items() if key != "results"}
        values["results"] = compact_rows
        data["values"] = values
    return data
