"""Strict model-directed planning for the small Step 6 read-only allowlist."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .contracts import STATE_TOOL_NAMES, StateNeedsPlan, ToolResult
from .investigation import InvestigationPlanError, validate_steps


MAX_STATE_TOOLS = len(STATE_TOOL_NAMES)
MAX_PRIOR_CONTEXT_CHARS = 8_000
MAX_FACT_STEPS = 4
MAX_FREEFORM_RCON_CHARS = 12_000
FACT_OPERATIONS = frozenset({
    "runtime_identity", "server_identity", "player_history",
    "list_admins", "player_permissions", "player_permissions_help",
})
SUBJECTS = frozenset({
    "jimbo", "server", "server_owner", "factorio_admins", "named_player", "other",
})
SUBJECT_FACTS = {
    "jimbo": frozenset({"runtime_identity"}),
    "server": frozenset({"server_identity"}),
    "server_owner": frozenset({"server_identity"}),
    "factorio_admins": frozenset({"list_admins"}),
    "named_player": frozenset({
        "player_history", "player_permissions", "player_permissions_help",
    }),
}


class StatePlanError(ValueError):
    """Raised when provider output is not exactly the safe planning schema."""


def validate_state_plan(raw: str) -> StateNeedsPlan:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise StatePlanError("state plan is not valid JSON") from error
    if (
        not isinstance(value, dict)
        or not set(value) <= {"subjects", "tools", "steps", "facts", "rcon"}
        or not {"subjects", "tools"} <= set(value)
    ):
        raise StatePlanError("state plan must contain subjects, tools, and optional steps/facts only")
    subjects = value["subjects"]
    if (
        not isinstance(subjects, list) or not subjects
        or not all(isinstance(subject, str) and subject in SUBJECTS for subject in subjects)
        or len(subjects) != len(set(subjects))
    ):
        raise StatePlanError("state plan subjects are invalid")
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
    raw_steps, raw_facts = _normalize_fact_placement(
        value.get("steps", []), value.get("facts", [])
    )
    try:
        steps = validate_steps(raw_steps)
    except InvestigationPlanError as error:
        raise StatePlanError(str(error)) from error
    facts = _validate_fact_steps(raw_facts)
    rcon_command = _validate_rcon(value.get("rcon"))
    fact_ops = {str(fact["op"]) for fact in facts}
    subjects = list(subjects)
    if "list_admins" in fact_ops:
        if "factorio_admins" not in subjects:
            subjects.append("factorio_admins")
        if "server" in subjects and "server_identity" not in fact_ops:
            subjects.remove("server")
    for subject in subjects:
        required = SUBJECT_FACTS.get(subject)
        if required is not None and not fact_ops.intersection(required):
            raise StatePlanError(f"subject {subject} lacks a compatible authoritative fact")
    if "runtime_identity" in fact_ops and "jimbo" not in subjects:
        raise StatePlanError("runtime identity fact requires the jimbo subject")
    if "server_identity" in fact_ops and not {"server", "server_owner"}.intersection(subjects):
        raise StatePlanError("server identity fact requires a server subject")
    if "named_player" not in subjects and fact_ops.intersection(SUBJECT_FACTS["named_player"]):
        raise StatePlanError("named-player fact requires the named_player subject")
    return StateNeedsPlan(
        tuple(tools), tuple(step.to_data() for step in steps), facts,
        tuple(subjects), rcon_command,
    )


def _validate_rcon(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise StatePlanError("rcon must be a non-empty string or null")
    command = raw.strip()
    if len(command) > MAX_FREEFORM_RCON_CHARS:
        raise StatePlanError("rcon command is too long")
    if "\r" in command or "\n" in command:
        raise StatePlanError("rcon command must be one physical line")
    if not command.startswith("/"):
        raise StatePlanError("rcon command must begin with /")
    return command


def _normalize_fact_placement(
    raw_steps: object, raw_facts: object
) -> tuple[object, object]:
    """Move unmistakable allowlisted fact operations out of the investigation list."""
    if not isinstance(raw_steps, list) or not isinstance(raw_facts, list):
        return raw_steps, raw_facts
    steps: list[object] = []
    facts: list[object] = list(raw_facts)
    for value in raw_steps:
        if isinstance(value, dict) and value.get("op") in FACT_OPERATIONS:
            fact = dict(value)
            fact.pop("domain", None)
            facts.append(fact)
        else:
            steps.append(value)
    return steps, facts


def _validate_fact_steps(raw: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(raw, list) or len(raw) > MAX_FACT_STEPS:
        raise StatePlanError("facts must be a bounded list")
    result: list[Mapping[str, object]] = []
    for value in raw:
        if not isinstance(value, dict) or not isinstance(value.get("op"), str):
            raise StatePlanError("each fact step must contain an operation")
        op = value["op"]
        if op not in FACT_OPERATIONS:
            raise StatePlanError("fact step contains an unknown operation")
        allowed = {"op"}
        if op in {"player_history", "player_permissions"}:
            allowed.add("player")
        if op == "list_admins":
            allowed.add("connected_only")
        if op == "player_permissions":
            allowed.add("action")
        if set(value) - allowed:
            raise StatePlanError("fact step contains extra fields")
        if op in {"player_history", "player_permissions"}:
            player = value.get("player")
            if (
                not isinstance(player, str) or not player.strip() or len(player) > 100
                or player.strip().casefold() in {"*", "?", "all", "any", "anyone", "players"}
                or any(marker in player for marker in ("*", "?"))
            ):
                raise StatePlanError("fact step requires an exact player name")
        connected_only = value.get("connected_only")
        if connected_only is not None and not isinstance(connected_only, bool):
            raise StatePlanError("connected_only must be a boolean")
        action = value.get("action")
        if action is not None and (
            not isinstance(action, str) or not action.strip() or len(action) > 100
            or not action.replace("_", "").replace("-", "").isalnum()
        ):
            raise StatePlanError("permission action is invalid")
        result.append(dict(value))
    return tuple(result)


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
