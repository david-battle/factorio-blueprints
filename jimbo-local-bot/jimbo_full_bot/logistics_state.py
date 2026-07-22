"""Bounded read-only logistic-network and logistic-container investigation."""

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
LOGISTICS_MARKER = "JIMBO_LOGISTICS_JSON|"
LOGISTICS_RESULT_RE = re.compile(r"JIMBO_LOGISTICS_JSON\|(?P<json>[\[{].*[\]}])")
LOGISTICS_NETWORK_COMMAND = (
    '/silent-command local o={networks={},containers={},warnings={}} local f=game.forces.player '
    'for s,a in pairs(f.logistic_networks) do for _,n in pairs(a) do if #o.networks==32 then '
    'o.warnings[1]="network limit reached" break end local p=n.cells[1] and n.cells[1].owner and '
    'n.cells[1].owner.position or nil local x={id=n.network_id,name=n.custom_name,surface=s,position=p,'
    'available_logistic_robots=n.available_logistic_robots,total_logistic_robots=n.all_logistic_robots,'
    'available_construction_robots=n.available_construction_robots,total_construction_robots=n.all_construction_robots,'
    'roboports=#n.cells,providers=#n.providers,requesters=#n.requesters,storages=#n.storages,contents={}} '
    'for _,v in pairs(n.get_contents()) do if #x.contents==128 then x.contents_partial=true break end '
    'x.contents[#x.contents+1]=v end o.networks[#o.networks+1]=x end if #o.networks==32 then break end end '
    'rcon.print("JIMBO_LOGISTICS_JSON|"..helpers.table_to_json(o))'
)
LOGISTICS_CONTAINER_COMMAND = (
    '/silent-command local o={networks={},containers={},warnings={}} local f=game.forces.player '
    'for s,v in pairs(game.surfaces) do for _,e in pairs(v.find_entities_filtered{force=f,type="logistic-container"}) do '
    'if #o.containers==64 then o.warnings[1]="container limit reached" break end local x={unit_number=e.unit_number,'
    'prototype=e.name,surface=s,position=e.position,network_id=e.logistic_network and e.logistic_network.network_id or nil,'
    'inventory={}} local i=e.get_inventory(defines.inventory.chest) if i then for _,z in pairs(i.get_contents()) do '
    'if #x.inventory==32 then x.inventory_partial=true break end x.inventory[#x.inventory+1]=z end end '
    'o.containers[#o.containers+1]=x end if #o.containers==64 then break end end '
    'rcon.print("JIMBO_LOGISTICS_JSON|"..helpers.table_to_json(o))'
)
LOGISTICS_REQUEST_COMMAND = (
    '/silent-command local o={networks={},containers={},warnings={}} local f=game.forces.player '
    'for s,v in pairs(game.surfaces) do for _,e in pairs(v.find_entities_filtered{force=f,type="logistic-container"}) do '
    'if #o.containers==64 then o.warnings[1]="container limit reached" break end local x={unit_number=e.unit_number,'
    'prototype=e.name,surface=s,position=e.position,network_id=e.logistic_network and e.logistic_network.network_id or nil,requests={}} '
    'local l=e.get_logistic_sections() if l then for _,a in pairs(l.sections) do for _,q in pairs(a.filters) do '
    'if #x.requests==32 then x.requests_partial=true break end if q.value then x.requests[#x.requests+1]={'
    'name=q.value.name,quality=q.value.quality,min=q.min,max=q.max} end end end end '
    'o.containers[#o.containers+1]=x end if #o.containers==64 then break end end '
    'rcon.print("JIMBO_LOGISTICS_JSON|"..helpers.table_to_json(o))'
)
SAFE_PROTOTYPE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


def _count_command(item: str, member: str) -> str:
    if not SAFE_PROTOTYPE_RE.fullmatch(item):
        raise LogisticsStateError("item prototype is not safe for the fixed count template")
    member_arg = "" if member == "all" else f',"{member}"'
    return (
        '/silent-command local o={networks={},containers={},warnings={}} local f=game.forces.player '
        'for s,a in pairs(f.logistic_networks) do for _,n in pairs(a) do if #o.networks==32 then '
        'o.warnings[1]="network limit reached" break end o.networks[#o.networks+1]={id=n.network_id,'
        'name=n.custom_name,surface=s,position=n.cells[1] and n.cells[1].owner and n.cells[1].owner.position or nil,'
        f'count=n.get_item_count("{item}"{member_arg})' + '} end if #o.networks==32 then break end end '
        'rcon.print("JIMBO_LOGISTICS_JSON|"..helpers.table_to_json(o))'
    )


def _container_command(step: InvestigationStep, *, requests: bool) -> str:
    for value in (step.surface, step.prototype, step.item):
        if value is not None and not SAFE_PROTOTYPE_RE.fullmatch(value):
            raise LogisticsStateError("container filter is not safe for the fixed template")
    surfaces = (
        f'local s=game.surfaces["{step.surface}"] local ss=s and {{s}} or {{}} '
        if step.surface else 'local ss=game.surfaces '
    )
    name_filter = f',name="{step.prototype}"' if step.prototype else ""
    network_filter = (
        f'e.logistic_network and e.logistic_network.network_id=={step.network}'
        if isinstance(step.network, int) else "true"
    )
    identity = ('unit_number=e.unit_number,prototype=e.name,surface=s.name,position=e.position,'
                'network_id=e.logistic_network and e.logistic_network.network_id or nil')
    if requests:
        body = (
            f'local x={{{identity},requests={{}}}} local l=e.get_logistic_sections() if l then '
            'for _,a in pairs(l.sections) do for _,q in pairs(a.filters) do if #x.requests==32 then '
            'x.requests_partial=true break end if q.value then '
            + (f'if q.value.name=="{step.item}" then ' if step.item else '') +
            'x.requests[#x.requests+1]={name=q.value.name,quality=q.value.quality,min=q.min,max=q.max}' +
            (' end' if step.item else '') + ' end end end end '
        )
    else:
        if step.item:
            inventory = (f'local c=i and i.get_item_count("{step.item}") or 0 '
                         f'if c>0 then x.inventory[1]={{name="{step.item}",quality="all",count=c}} end ')
        else:
            inventory = ('if i then for _,z in pairs(i.get_contents()) do if #x.inventory==32 then '
                         'x.inventory_partial=true break end x.inventory[#x.inventory+1]=z end end ')
        body = f'local x={{{identity},inventory={{}}}} local i=e.get_inventory(defines.inventory.chest) ' + inventory
    return (
        '/silent-command local o={networks={},containers={},warnings={}} local f=game.forces.player ' +
        surfaces + f'for _,s in pairs(ss) do for _,e in pairs(s.find_entities_filtered{{force=f,type="logistic-container"{name_filter}}}) do '
        f'if {network_filter} then if #o.containers==128 then o.warnings[1]="container limit reached" break end ' +
        body + 'o.containers[#o.containers+1]=x end end if #o.containers==128 then break end end '
        'rcon.print("JIMBO_LOGISTICS_JSON|"..helpers.table_to_json(o))'
    )


class LogisticsStateError(RuntimeError):
    """Raised when the fixed logistics snapshot cannot be collected."""


class LogisticsInvestigationProvider:
    def __init__(self, *, wrapper_path: Path, command_path: Path, timeout_seconds: float) -> None:
        self.wrapper_path = wrapper_path
        self.command_path = command_path
        self.timeout_seconds = timeout_seconds

    def collect(self, command: str = LOGISTICS_NETWORK_COMMAND) -> Mapping[str, object]:
        original = self.command_path.read_bytes()
        try:
            self.command_path.write_text(command + "\n", encoding="utf-8")
            completed = subprocess.run(
                [str(POWERSHELL_PATH), "-NoProfile", "-File", str(self.wrapper_path)],
                capture_output=True, text=True, timeout=self.timeout_seconds, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise LogisticsStateError(f"logistics query failed: {error}") from error
        finally:
            self.command_path.write_bytes(original)
        output = completed.stdout + "\n" + completed.stderr
        match = LOGISTICS_RESULT_RE.search(output)
        if completed.returncode != 0 or match is None:
            detail = " ".join(output.split())[-500:]
            raise LogisticsStateError(
                f"logistics query was not confirmed (exit {completed.returncode}): {detail}"
            )
        raw = match.group("json")
        if len(raw.encode("utf-8")) > MAX_RESULT_BYTES:
            raise LogisticsStateError("logistics query exceeded the result byte limit")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise LogisticsStateError("logistics query returned invalid JSON") from error
        if isinstance(value, dict):
            for key in ("networks", "containers", "warnings"):
                if value.get(key) == {}:
                    value[key] = []
        if not isinstance(value, dict) or not isinstance(value.get("networks"), list) or not isinstance(value.get("containers"), list):
            raise LogisticsStateError("logistics query returned an invalid shape")
        return value

    def execute(self, raw_steps: Sequence[Mapping[str, object]]) -> tuple[ToolResult, ...]:
        steps = validate_steps(list(raw_steps))
        if not steps or any(step.domain != "logistics" for step in steps):
            raise LogisticsStateError("logistics provider received an invalid domain")
        needs_network_snapshot = any(step.op != "count_items" for step in steps)
        snapshot = dict(self.collect(LOGISTICS_NETWORK_COMMAND)) if needs_network_snapshot else {
            "networks": [], "containers": [], "warnings": []
        }
        for step in (value for value in steps if value.op == "count_items"):
            counted = self.collect(_count_command(step.item or "", step.member or "all"))
            by_id = {n.get("id"): n for n in snapshot["networks"] if isinstance(n, dict)}
            for network in counted["networks"]:
                if isinstance(network, dict):
                    target = by_id.setdefault(network.get("id"), {})
                    count = network.get("count", 0)
                    target.update({key: value for key, value in network.items() if key != "count"})
                    counts = target.setdefault("counts", {})
                    if isinstance(counts, dict):
                        counts[(step.item or "") + "|" + (step.member or "all")] = count
            snapshot["networks"] = list(by_id.values())
            snapshot["warnings"] = list(snapshot.get("warnings", ())) + list(counted.get("warnings", ()))
        containers_by_step: dict[InvestigationStep, tuple[Mapping[str, object], ...]] = {}
        for step in (value for value in steps if value.op == "inspect_containers"):
            container_snapshots = [self.collect(_container_command(step, requests=False))]
            if "requests" in step.select:
                container_snapshots.append(self.collect(_container_command(step, requests=True)))
            merged_containers: dict[object, dict[str, object]] = {}
            for container_snapshot in container_snapshots:
                for container in container_snapshot["containers"]:
                    if isinstance(container, dict):
                        merged_containers.setdefault(container.get("unit_number"), {}).update(container)
                snapshot["warnings"] = list(snapshot.get("warnings", ())) + list(container_snapshot.get("warnings", ()))
            containers_by_step[step] = tuple(merged_containers.values())
        collected_at = datetime.now(UTC)
        warnings = [str(item) for item in snapshot.get("warnings", ()) if isinstance(item, str)]
        if any(isinstance(n, dict) and n.get("contents_partial") for n in snapshot["networks"]):
            warnings.append("one or more network inventories reached the 128-row limit")
        networks = tuple(n for n in snapshot["networks"] if isinstance(n, dict))
        containers = tuple(c for c in snapshot["containers"] if isinstance(c, dict))
        return tuple(_execute_step(
            step, networks, containers_by_step.get(step, containers), collected_at, tuple(warnings)
        ) for step in steps)


def _execute_step(step: InvestigationStep, networks: Sequence[Mapping[str, object]], containers: Sequence[Mapping[str, object]], collected_at: datetime, warnings: tuple[str, ...]) -> ToolResult:
    selected_networks = tuple(n for n in networks if _network_matches(n, step.network, step.surface))
    provenance = Provenance(
        source="fixed_read_only_rcon:logistics", collected_at=collected_at,
        scope="force=player;domain=logistics",
        filters=tuple(x for x in (
            f"network={step.network}" if step.network is not None else "",
            f"surface={step.surface}" if step.surface else "",
            f"item={step.item}" if step.item else "",
            f"prototype={step.prototype}" if step.prototype else "",
        ) if x), complete=not warnings,
    )
    if step.network is not None and not selected_networks:
        return ToolResult(ResultStatus.UNKNOWN, "No logistic network exactly matched the requested reference.", provenance,
                          {"operation": step.op, "candidates": [_network_identity(n) for n in networks]},
                          warnings + ("network reference did not match",))
    if step.op == "list_networks":
        payload = [{field: n.get(field) for field in step.select} for n in selected_networks]
        summary = f"Observed {len(payload)} logistic network(s)."
    elif step.op == "inspect_contents":
        payload = []
        for network in selected_networks:
            rows = network.get("contents", [])
            if not isinstance(rows, list): rows = []
            if step.item is not None:
                rows = [row for row in rows if isinstance(row, dict) and row.get("name") == step.item]
            payload.append({**_network_identity(network), "items": [
                {field: row.get(field) for field in step.select} for row in rows if isinstance(row, dict)
            ]})
        summary = f"Inspected contents for {len(selected_networks)} logistic network(s)."
    elif step.op == "count_items":
        count_key = (step.item or "") + "|" + (step.member or "all")
        payload = [{**_network_identity(network), "item": step.item,
                    "member": step.member, "count": network.get("counts", {}).get(count_key, 0)}
                   for network in selected_networks]
        summary = f"Counted {step.item} in {len(selected_networks)} logistic network(s)."
    else:
        network_ids = {n.get("id") for n in selected_networks}
        matched = [c for c in containers if (step.network is None or c.get("network_id") in network_ids)
                   and (step.surface is None or c.get("surface") == step.surface)
                   and (step.prototype is None or c.get("prototype") == step.prototype)]
        payload = [{field: c.get(field) for field in step.select} for c in matched]
        summary = f"Inspected {len(payload)} bounded logistic container record(s)."
    return ToolResult(ResultStatus.PARTIAL if warnings else ResultStatus.COMPLETE, summary, provenance,
                      {"operation": step.op, "domain": step.domain, "results": payload}, warnings)


def _network_matches(network: Mapping[str, object], reference: int | str | None, surface: str | None) -> bool:
    return (reference is None or network.get("id") == reference or network.get("name") == reference) and (surface is None or network.get("surface") == surface)


def _network_identity(network: Mapping[str, object]) -> dict[str, object]:
    return {"id": network.get("id"), "name": network.get("name"), "surface": network.get("surface"), "position": network.get("position")}
