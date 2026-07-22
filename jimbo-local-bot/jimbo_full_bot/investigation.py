"""Minimal bounded investigation schema and application-owned capability catalog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


MAX_STEPS = 6
MAX_SELECT_FIELDS = 12
PLATFORM_FIELDS = (
    "id", "name", "surface", "state", "paused", "speed", "weight",
    "location", "location_kind", "last_location", "connection",
    "connection_from", "connection_to", "distance", "has_hub",
)
INVENTORY_FIELDS = ("name", "quality", "count")
REQUEST_FIELDS = ("name", "quality", "min", "max", "import_from")
SCHEDULE_FIELDS = ("current", "records")
NETWORK_FIELDS = (
    "id", "name", "surface", "position", "available_logistic_robots",
    "total_logistic_robots", "available_construction_robots",
    "total_construction_robots", "roboports", "providers", "requesters",
    "storages",
)
CONTAINER_FIELDS = (
    "unit_number", "prototype", "surface", "position", "network_id",
    "inventory", "requests",
)
CAPABILITY_CATALOG: Mapping[str, object] = {
    "space_platforms": {
        "identity_note": "name is the displayed platform name; surface is its internal surface identifier",
        "operations": {
            "list_objects": {"select": list(PLATFORM_FIELDS)},
            "inspect_inventory": {"optional": ["platform", "item", "select"], "select": list(INVENTORY_FIELDS)},
            "list_requests": {"optional": ["platform", "item", "select"], "select": list(REQUEST_FIELDS)},
            "get_schedule": {"optional": ["platform", "select"], "select": list(SCHEDULE_FIELDS)},
        },
        "platform_reference": "an exact platform index integer or exact displayed name string",
        "location_note": "location_kind says stopped_at_location, in_transit, or platform_surface_only; surface is the platform's own map surface, not a planet claim",
    },
    "logistics": {
        "operations": {
            "list_networks": {"optional": ["surface", "select"], "select": list(NETWORK_FIELDS)},
            "inspect_contents": {"optional": ["network", "surface", "item", "select"], "select": list(INVENTORY_FIELDS)},
            "count_items": {"required": ["item"], "optional": ["network", "surface", "member"], "member": ["all", "providers", "storage"]},
            "inspect_containers": {"optional": ["network", "surface", "prototype", "item", "select"], "select": list(CONTAINER_FIELDS)},
        },
        "network_reference": "an exact logistic network ID integer or exact custom name string",
        "limits": "at most 32 networks, 128 item rows per network, and 64 logistic containers per snapshot; warnings mark partial results",
    }
}


class InvestigationPlanError(ValueError):
    """Raised when a model proposal is outside the registered query schema."""


@dataclass(frozen=True, slots=True)
class InvestigationStep:
    op: str
    domain: str
    select: tuple[str, ...] = ()
    platform: int | str | None = None
    network: int | str | None = None
    surface: str | None = None
    item: str | None = None
    prototype: str | None = None
    member: str | None = None

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {"op": self.op, "domain": self.domain}
        if self.select:
            data["select"] = list(self.select)
        if self.platform is not None:
            data["platform"] = self.platform
        if self.network is not None:
            data["network"] = self.network
        if self.surface is not None:
            data["surface"] = self.surface
        if self.item is not None:
            data["item"] = self.item
        if self.prototype is not None:
            data["prototype"] = self.prototype
        if self.member is not None:
            data["member"] = self.member
        return data


def validate_steps(raw_steps: object) -> tuple[InvestigationStep, ...]:
    if not isinstance(raw_steps, list):
        raise InvestigationPlanError("steps must be a list")
    if len(raw_steps) > MAX_STEPS:
        raise InvestigationPlanError("investigation has too many steps")
    return tuple(_validate_step(value) for value in raw_steps)


def _validate_step(value: object) -> InvestigationStep:
    if not isinstance(value, dict):
        raise InvestigationPlanError("each investigation step must be an object")
    op = value.get("op")
    domain = value.get("domain")
    if not isinstance(op, str) or domain not in {"space_platforms", "logistics"}:
        raise InvestigationPlanError("unknown investigation operation or domain")
    if domain == "logistics":
        return _validate_logistics_step(value, op, domain)
    common = {"op", "domain"}
    if op == "list_objects":
        extra = set(value) - (common | {"select"})
        if extra:
            raise InvestigationPlanError(
                "list_objects contains extra fields: " + ",".join(sorted(extra))
            )
        select = value.get("select", list(PLATFORM_FIELDS))
        if (
            not isinstance(select, list)
            or not select
            or len(select) > MAX_SELECT_FIELDS
            or not all(isinstance(field, str) and field in PLATFORM_FIELDS for field in select)
            or len(set(select)) != len(select)
        ):
            raise InvestigationPlanError("list_objects select is invalid")
        return InvestigationStep(op, domain, tuple(select))
    if op not in {"inspect_inventory", "list_requests", "get_schedule"}:
        raise InvestigationPlanError("unknown investigation operation")
    allowed = common | {"platform", "select"}
    if op != "get_schedule":
        allowed.add("item")
    extra = set(value) - allowed
    if extra:
        raise InvestigationPlanError(
            f"{op} contains extra fields: " + ",".join(sorted(extra))
        )
    platform = value.get("platform")
    if platform is not None and (
        isinstance(platform, bool)
        or not isinstance(platform, (int, str))
        or isinstance(platform, int) and platform < 1
        or isinstance(platform, str) and (not platform.strip() or len(platform) > 100)
    ):
        raise InvestigationPlanError("platform reference is invalid")
    item = value.get("item")
    if item is not None and (
        not isinstance(item, str) or not item or len(item) > 100
    ):
        raise InvestigationPlanError("item filter is invalid")
    allowed_select = {
        "inspect_inventory": INVENTORY_FIELDS,
        "list_requests": REQUEST_FIELDS,
        "get_schedule": SCHEDULE_FIELDS,
    }[op]
    select = value.get("select", list(allowed_select))
    if (
        not isinstance(select, list)
        or not select
        or not all(isinstance(field, str) and field in allowed_select for field in select)
        or len(set(select)) != len(select)
    ):
        raise InvestigationPlanError(f"{op} select is invalid")
    return InvestigationStep(op, domain, tuple(select), platform=platform, item=item)


def _validate_logistics_step(value: dict[str, object], op: str, domain: str) -> InvestigationStep:
    if op not in {"list_networks", "inspect_contents", "count_items", "inspect_containers"}:
        raise InvestigationPlanError("unknown logistics operation")
    allowed = {"op", "domain", "select", "surface"}
    if op != "list_networks":
        allowed.add("network")
    if op in {"inspect_contents", "count_items", "inspect_containers"}:
        allowed.add("item")
    if op == "count_items":
        allowed.add("member")
    if op == "inspect_containers":
        allowed.add("prototype")
    extra = set(value) - allowed
    if extra:
        raise InvestigationPlanError(
            f"{op} contains extra fields: " + ",".join(sorted(extra))
        )
    network = value.get("network")
    if network is not None and (
        isinstance(network, bool) or not isinstance(network, (int, str))
        or isinstance(network, int) and network < 1
        or isinstance(network, str) and (not network.strip() or len(network) > 100)
    ):
        raise InvestigationPlanError("network reference is invalid")
    surface = value.get("surface")
    item = value.get("item")
    prototype = value.get("prototype")
    for label, candidate in (("surface", surface), ("item", item), ("prototype", prototype)):
        if candidate is not None and (
            not isinstance(candidate, str) or not candidate.strip() or len(candidate) > 100
        ):
            raise InvestigationPlanError(f"{label} filter is invalid")
    member = value.get("member")
    if op == "count_items" and (item is None or member not in {None, "all", "providers", "storage"}):
        raise InvestigationPlanError("count_items requires item and a valid optional member")
    if op == "count_items":
        if "select" in value:
            raise InvestigationPlanError("count_items does not accept select")
        return InvestigationStep(
            op, domain, network=network, surface=surface, item=item,
            member=member or "all",
        )
    fields = {
        "list_networks": NETWORK_FIELDS,
        "inspect_contents": INVENTORY_FIELDS,
        "inspect_containers": CONTAINER_FIELDS,
    }[op]
    select = value.get("select", list(fields))
    if (
        not isinstance(select, list) or not select or len(select) > MAX_SELECT_FIELDS
        or not all(isinstance(field, str) and field in fields for field in select)
        or len(set(select)) != len(select)
    ):
        raise InvestigationPlanError(f"{op} select is invalid")
    return InvestigationStep(
        op, domain, tuple(select), network=network, surface=surface,
        item=item, prototype=prototype, member=member,
    )
