"""Bounded fixed read-only platform snapshot and generic step projections."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from .contracts import Provenance, ResultStatus, ToolResult
from .delivery import POWERSHELL_PATH
from .investigation import InvestigationStep, validate_steps


MAX_RESULT_BYTES = 200_000
PLATFORM_MARKER = "JIMBO_PLATFORM_JSON|"
PLATFORM_RESULT_RE = re.compile(r"JIMBO_PLATFORM_JSON\|(?P<json>[\[{].*[\]}])")
PLATFORM_OBJECT_COMMAND = (
    '/silent-command local o={} for _,p in pairs(game.forces.player.platforms) do if #o>=16 then break end '
    'local x={index=p.index,name=p.name,state=p.state,paused=p.paused,speed=p.speed,weight=p.weight,'
    'surface=p.surface and p.surface.name or nil,loc=p.space_location and p.space_location.name or nil,'
    'prev=p.last_visited_space_location and p.last_visited_space_location.name or nil,'
    'conn=p.space_connection and p.space_connection.name or nil,'
    'from=p.space_connection and p.space_connection.from.name or nil,'
    'to=p.space_connection and p.space_connection.to.name or nil,'
    'kind=p.space_location and "stopped_at_location" or (p.space_connection and "in_transit" or "platform_surface_only"),'
    'distance=p.distance,has_hub=p.hub~=nil} o[#o+1]=x end '
    'rcon.print("JIMBO_PLATFORM_JSON|"..helpers.table_to_json(o))'
)
PLATFORM_DETAIL_COMMAND = (
    '/silent-command local o={} for _,p in pairs(game.forces.player.platforms) do if #o>=16 then break end '
    'local x={index=p.index,name=p.name,surface=p.surface and p.surface.name or nil,has_hub=p.hub~=nil,'
    'schedule=p.schedule,inventory={},requests={}} if p.hub then local i=p.hub.get_inventory(defines.inventory.hub_main) '
    'x.inventory=i and i.get_contents() or {} local l=p.hub.get_logistic_sections() if l then for _,s in pairs(l.sections) do '
    'for _,f in pairs(s.filters) do if f.value then x.requests[#x.requests+1]={name=f.value.name,quality=f.value.quality,'
    'min=f.min,max=f.max,import_from=f.import_from} end end end end end o[#o+1]=x end '
    'rcon.print("JIMBO_PLATFORM_JSON|"..helpers.table_to_json(o))'
)


class PlatformStateError(RuntimeError):
    pass


class PlatformInvestigationProvider:
    def __init__(self, *, wrapper_path: Path, command_path: Path, timeout_seconds: float) -> None:
        self.wrapper_path = wrapper_path
        self.command_path = command_path
        self.timeout_seconds = timeout_seconds

    def collect(self, command: str = PLATFORM_OBJECT_COMMAND) -> Mapping[str, object]:
        original = self.command_path.read_bytes()
        try:
            self.command_path.write_text(command + "\n", encoding="utf-8")
            completed = subprocess.run(
                [str(POWERSHELL_PATH), "-NoProfile", "-File", str(self.wrapper_path)],
                capture_output=True, text=True, timeout=self.timeout_seconds, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PlatformStateError(f"platform query failed: {error}") from error
        finally:
            self.command_path.write_bytes(original)
        output = completed.stdout + "\n" + completed.stderr
        match = PLATFORM_RESULT_RE.search(output)
        if completed.returncode != 0 or match is None:
            detail = " ".join(output.split())[-500:]
            raise PlatformStateError(
                f"platform query was not confirmed (exit {completed.returncode}): {detail}"
            )
        raw = match.group("json")
        if len(raw.encode("utf-8")) > MAX_RESULT_BYTES:
            raise PlatformStateError("platform query exceeded the result byte limit")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise PlatformStateError("platform query returned invalid JSON") from error
        if isinstance(value, list):
            value = {"platforms": value, "warnings": []}
        if not isinstance(value, dict) or not isinstance(value.get("platforms"), list):
            raise PlatformStateError("platform query returned an invalid shape")
        warnings = value.setdefault("warnings", [])
        if len(value["platforms"]) >= 16:
            warnings.append("platform limit may have been reached")
        for platform in value["platforms"]:
            if not isinstance(platform, dict):
                continue
            for field, limit in (("inventory", 128), ("requests", 64)):
                rows = platform.get(field, [])
                if isinstance(rows, list) and len(rows) > limit:
                    platform[field] = rows[:limit]
                    warnings.append(f"{field} row limit reached")
        return value

    def execute(self, raw_steps: Sequence[Mapping[str, object]]) -> tuple[ToolResult, ...]:
        steps = validate_steps(list(raw_steps))
        if not steps or any(step.domain != "space_platforms" for step in steps):
            raise PlatformStateError("platform provider received an invalid domain")
        snapshots = []
        if any(step.op == "list_objects" for step in steps):
            snapshots.append(self.collect(PLATFORM_OBJECT_COMMAND))
        if any(step.op != "list_objects" for step in steps):
            snapshots.append(self.collect(PLATFORM_DETAIL_COMMAND))
        snapshot = _merge_snapshots(snapshots)
        collected_at = datetime.now(UTC)
        warnings = tuple(str(item) for item in snapshot.get("warnings", ()) if isinstance(item, str))
        platforms = tuple(item for item in snapshot["platforms"] if isinstance(item, dict))
        return tuple(_execute_step(step, platforms, collected_at, warnings) for step in steps)


def _execute_step(
    step: InvestigationStep,
    platforms: Sequence[Mapping[str, object]],
    collected_at: datetime,
    snapshot_warnings: tuple[str, ...],
) -> ToolResult:
    selected = _select_platforms(platforms, step.platform)
    provenance = Provenance(
        source="fixed_read_only_rcon:space_platforms",
        collected_at=collected_at,
        scope="force=player;domain=space_platforms",
        filters=tuple(
            value for value in (
                f"platform={step.platform}" if step.platform is not None else "",
                f"item={step.item}" if step.item is not None else "",
            ) if value
        ),
        complete=not snapshot_warnings,
    )
    if step.platform is not None and not selected:
        return ToolResult(
            ResultStatus.UNKNOWN,
            "No platform exactly matched the requested reference.",
            provenance,
            {"operation": step.op, "candidates": [_identity(p) for p in platforms]},
            snapshot_warnings + ("platform reference did not match",),
        )
    if step.op == "list_objects":
        select = list(step.select)
        location_fields = (
            "location_kind", "location", "connection", "connection_from",
            "connection_to", "distance", "state", "surface",
        )
        if any(field in step.select for field in location_fields[:-2]):
            select = list(dict.fromkeys(("id", "name", *select, *location_fields)))
        values = [{field: _field(platform, field) for field in select} for platform in selected]
        summary = f"Observed {len(values)} space platform(s)."
        payload: object = values
    elif step.op == "inspect_inventory":
        payload = [_inventory(platform, step.item, step.select) for platform in selected]
        summary = f"Inspected hub inventory for {len(selected)} space platform(s)."
    elif step.op == "list_requests":
        payload = [_requests(platform, step.item, step.select) for platform in selected]
        summary = f"Inspected logistic requests for {len(selected)} space platform(s)."
    else:
        payload = []
        for platform in selected:
            schedule = platform.get("schedule", {})
            if not isinstance(schedule, dict):
                schedule = {}
            payload.append({
                **_identity(platform),
                "schedule": {field: schedule.get(field) for field in step.select},
            })
        summary = f"Inspected schedules for {len(selected)} space platform(s)."
    result_values: dict[str, object] = {"operation": step.op, "domain": step.domain, "results": payload}
    if step.op == "list_objects":
        result_values["location_semantics"] = {
            "stopped_at_location": "stopped in orbit at the named space location, not on the planet surface",
            "in_transit": "traveling along connection_from to connection_to; distance is 0 at from and 1 at to",
            "platform_surface_only": "the platform map surface exists but no stopped location or transit connection was reported",
        }
    return ToolResult(
        ResultStatus.PARTIAL if snapshot_warnings else ResultStatus.COMPLETE,
        summary,
        provenance,
        result_values,
        snapshot_warnings,
    )


def _merge_snapshots(snapshots: Sequence[Mapping[str, object]]) -> dict[str, object]:
    merged: dict[object, dict[str, object]] = {}
    warnings: list[object] = []
    for snapshot in snapshots:
        warnings.extend(snapshot.get("warnings", ()))
        for platform in snapshot.get("platforms", ()):
            if isinstance(platform, dict):
                merged.setdefault(platform.get("index"), {}).update(platform)
    return {"platforms": list(merged.values()), "warnings": warnings}


def _select_platforms(
    platforms: Sequence[Mapping[str, object]], reference: int | str | None
) -> tuple[Mapping[str, object], ...]:
    if reference is None:
        return tuple(platforms)
    return tuple(
        platform for platform in platforms
        if platform.get("index") == reference or platform.get("name") == reference
    )


def _identity(platform: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": platform.get("index"),
        "name": platform.get("name"),
        "surface": platform.get("surface"),
    }


def _field(platform: Mapping[str, object], field: str) -> object:
    return platform.get({
        "id": "index", "location": "loc", "location_kind": "kind",
        "last_location": "prev", "connection": "conn",
        "connection_from": "from", "connection_to": "to",
    }.get(field, field))


def _inventory(
    platform: Mapping[str, object], item: str | None, select: Sequence[str]
) -> dict[str, object]:
    rows = platform.get("inventory", [])
    if not isinstance(rows, list):
        rows = []
    if item is not None:
        rows = [row for row in rows if isinstance(row, dict) and row.get("name") == item]
    rows = [
        {field: row.get(field) for field in select}
        for row in rows if isinstance(row, dict)
    ]
    return {**_identity(platform), "has_hub": platform.get("has_hub", False), "items": rows}


def _requests(
    platform: Mapping[str, object], item: str | None, select: Sequence[str]
) -> dict[str, object]:
    rows = platform.get("requests", [])
    if not isinstance(rows, list):
        rows = []
    if item is not None:
        rows = [row for row in rows if isinstance(row, dict) and row.get("name") == item]
    rows = [
        {field: row.get(field) for field in select}
        for row in rows if isinstance(row, dict)
    ]
    return {**_identity(platform), "has_hub": platform.get("has_hub", False), "requests": rows}
