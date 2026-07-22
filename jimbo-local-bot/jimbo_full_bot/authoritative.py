"""Application-owned runtime, history, identity, and permission facts."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from .archive import TextEventArchive
from .config import FullBotConfig, REPOSITORY_ROOT
from .contracts import EventKind, NormalizedEvent, Provenance, ResultStatus, ToolResult
from .delivery import POWERSHELL_PATH


PERMISSION_RESULT_RE = re.compile(r"JIMBO_PERMISSIONS\|(?P<json>\{.*\})")
ADMIN_ACTION_ALIASES = frozenset({"ban", "kick", "promote", "demote"})


class AuthoritativeFactError(RuntimeError):
    """Raised when an authoritative fact source cannot be read."""


class PermissionProvider:
    def __init__(self, *, wrapper_path: Path, command_path: Path, timeout_seconds: float) -> None:
        self.wrapper_path = wrapper_path
        self.command_path = command_path
        self.timeout_seconds = timeout_seconds

    def execute(self, steps: Sequence[Mapping[str, object]]) -> tuple[ToolResult, ...]:
        if not steps:
            return ()
        results: list[ToolResult] = []
        original = self.command_path.read_bytes()
        try:
            for step in steps:
                self.command_path.write_text(_permission_command(step) + "\n", encoding="utf-8")
                completed = subprocess.run(
                    [str(POWERSHELL_PATH), "-NoProfile", "-File", str(self.wrapper_path)],
                    capture_output=True, text=True, timeout=self.timeout_seconds, check=False,
                )
                output = (completed.stdout + "\n" + completed.stderr).strip()
                match = PERMISSION_RESULT_RE.search(output)
                if completed.returncode != 0 or match is None:
                    raise AuthoritativeFactError(
                        f"permission query was not confirmed (exit {completed.returncode})"
                    )
                try:
                    payload = json.loads(match.group("json"))
                except json.JSONDecodeError as error:
                    raise AuthoritativeFactError("permission query returned invalid JSON") from error
                results.append(_permission_result(step, payload))
        except (OSError, subprocess.SubprocessError) as error:
            raise AuthoritativeFactError(f"permission query failed: {error}") from error
        finally:
            self.command_path.write_bytes(original)
        return tuple(results)


class AuthoritativeFactProvider:
    def __init__(
        self,
        config: FullBotConfig,
        archive: TextEventArchive,
        history_events: Sequence[NormalizedEvent],
        model: object,
        permissions: PermissionProvider,
    ) -> None:
        self.config = config
        self.archive = archive
        self.history_events = tuple(history_events)
        self.model = model
        self.permissions = permissions

    def execute(
        self, steps: Sequence[Mapping[str, object]], *, subjects: Sequence[str] = ()
    ) -> tuple[ToolResult, ...]:
        results: list[ToolResult] = []
        permission_steps: list[Mapping[str, object]] = []
        for step in steps:
            op = str(step["op"])
            if op == "runtime_identity":
                results.append(self._runtime_identity())
            elif op == "server_identity":
                results.append(self._server_identity(subjects))
            elif op == "player_history":
                results.append(self._player_history(str(step["player"])))
            elif op == "player_permissions_help":
                results.append(self._player_permissions_help())
            elif op in {"list_admins", "player_permissions"}:
                permission_steps.append(step)
            else:
                raise ValueError(f"unsupported authoritative fact: {op}")
        if permission_steps:
            results.extend(self.permissions.execute(permission_steps))
        return tuple(results)

    def _runtime_identity(self) -> ToolResult:
        records = self.archive.scan().records
        usage = getattr(self.model, "last_usage", {})
        quota = getattr(self.model, "last_rate_limits", {})
        values: dict[str, object] = {
            "operation": "runtime_identity",
            "identity": "Jimbo the Jr. Engineer",
            "server_owner": self.config.management_player,
            "jimbo_operator": self.config.management_player,
            "provider": self.config.provider,
            "model": self.config.model,
            "model_parameter_count": None,
            "factorio_version": "2.1.12",
            "expansion": "Space Age",
            "features": ["Elevated Rails", "Quality"],
            "conversation_memory": "last 3 delivered exchanges per player; lost on restart",
            "seen_player_memory": "permanent flat-text state reconstructed from retained history",
            "archive_records": len(records),
            "archive_scope": "public chat, join/leave, and bot lifecycle records",
            "enabled_live_domains": ["server snapshot", "space platforms", "logistics", "permissions"],
            "world_actions": "no direct construction/removal; ghost actions are not yet active",
            "chat_character_limit": self.config.chat_character_limit,
            "provider_timeout_seconds": self.config.provider_timeout_seconds,
            "revision": _git_revision(REPOSITORY_ROOT),
            "observed_usage": dict(usage) if isinstance(usage, dict) else {},
            "observed_quota": dict(quota) if isinstance(quota, dict) else {},
            "renderer": "single-line ASCII-normalized Factorio chat with inert model-authored tags",
        }
        return ToolResult(
            ResultStatus.COMPLETE,
            f"Jimbo the Jr. Engineer runs {self.config.model} through {self.config.provider}; "
            "it remembers 3 delivered exchanges until restart, can inspect approved live "
            "state, and cannot kick or ban players.",
            Provenance.now("runtime_configuration", "bot=current-process"),
            values,
        )

    def _server_identity(self, subjects: Sequence[str] = ()) -> ToolResult:
        moderators = list(self.config.moderator_roster)
        if "server" in subjects:
            summary = (
                "This server runs Factorio 2.1.12 with Space Age, Elevated Rails, and "
                "Quality. It favors player freedom; humans decide acceptable behavior."
            )
        else:
            summary = f"{self.config.management_player} is the server owner and Jimbo operator."
        return ToolResult(
            ResultStatus.COMPLETE,
            summary,
            Provenance.now("human_authored_configuration", "server=identity-and-philosophy"),
            {
                "operation": "server_identity",
                "server_owner": self.config.management_player,
                "jimbo_operator": self.config.management_player,
                "moderator_roster": moderators,
                "philosophy": self.config.server_philosophy,
                "admin_separation": (
                    "Factorio admin flags do not confer server ownership, moderation, "
                    "or authority over Jimbo"
                ),
            },
        )

    def _player_history(self, requested_name: str) -> ToolResult:
        matches = [
            event for event in self.history_events
            if (event.actor or "").casefold() == requested_name.casefold()
            and event.kind in {EventKind.PUBLIC_CHAT, EventKind.PLAYER_JOIN, EventKind.PLAYER_LEAVE}
        ]
        provenance = Provenance.now(
            "retained_public_event_history", f"player={requested_name.casefold()}"
        )
        if not matches:
            return ToolResult(
                ResultStatus.UNKNOWN,
                f"No retained public chat, join, or leave evidence was found for {requested_name}.",
                provenance,
                {"operation": "player_history", "player": requested_name, "seen": False},
                ("absence from retained evidence does not prove the player never visited",),
            )
        matches.sort(key=lambda event: event.occurred_at)
        counts = {
            "public_chat": sum(event.kind is EventKind.PUBLIC_CHAT for event in matches),
            "joins": sum(event.kind is EventKind.PLAYER_JOIN for event in matches),
            "leaves": sum(event.kind is EventKind.PLAYER_LEAVE for event in matches),
        }
        display = matches[-1].actor or requested_name
        return ToolResult(
            ResultStatus.COMPLETE,
            f"{display} appears in retained public history; first seen "
            f"{_display_time(matches[0].occurred_at)}, last seen "
            f"{_display_time(matches[-1].occurred_at)}; {counts['joins']} joins, "
            f"{counts['leaves']} leaves, {counts['public_chat']} chat messages.",
            provenance,
            {
                "operation": "player_history", "player": display, "seen": True,
                "first_seen": matches[0].occurred_at.isoformat(),
                "last_seen": matches[-1].occurred_at.isoformat(), **counts,
            },
        )

    def _player_permissions_help(self) -> ToolResult:
        return ToolResult(
            ResultStatus.UNKNOWN,
            "I can inspect a player's current Factorio permissions; please give the exact player name.",
            Provenance.now("runtime_configuration", "permissions=exact-player-required"),
            {"operation": "player_permissions_help", "exact_player_required": True},
        )


def direct_fact_answer(results: Sequence[ToolResult]) -> str:
    """Format authoritative results without allowing model replacement."""
    return " ".join(result.summary for result in results)


def _permission_command(step: Mapping[str, object]) -> str:
    if step["op"] == "list_admins":
        players = "game.connected_players" if step.get("connected_only") is True else "game.players"
        return (
            '/silent-command local a={} for _,p in pairs(' + players + ') do if p.admin then '
            'a[#a+1]=p.name end end table.sort(a) rcon.print("JIMBO_PERMISSIONS|"..'
            'helpers.table_to_json({admins=a}))'
        )
    player = _lua_long_string(str(step["player"]))
    action = step.get("action")
    normalized = None if action is None else str(action).replace("-", "_")
    input_action = "admin_action" if normalized in ADMIN_ACTION_ALIASES else normalized
    base = (
        "/silent-command local p=game.get_player(" + player + ") local o={player=" + player
        + ",found=p~=nil} if p then local g=p.permission_group o.player=p.name o.admin=p.admin "
        'o.group=g and g.name or "Default" '
    )
    if input_action is not None:
        action_text = json.dumps(normalized or input_action)
        input_text = json.dumps(input_action)
        base += (
            "local i=defines.input_action[" + input_text + "] o.action=" + action_text
            + " o.input_action=" + input_text + " o.action_known=i~=nil "
            + "o.allowed=i~=nil and (not g or g.allows_action(i)) and ("
            + input_text + '~="admin_action" or p.admin) '
        )
    else:
        base += (
            "local d={} if g then for n,i in pairs(defines.input_action) do if not "
            "g.allows_action(i) then d[#d+1]=n end end table.sort(d) end o.denied_actions=d "
        )
    return base + 'end rcon.print("JIMBO_PERMISSIONS|"..helpers.table_to_json(o))'


def _permission_result(step: Mapping[str, object], row: object) -> ToolResult:
    if not isinstance(row, dict):
        raise AuthoritativeFactError("permission result shape is invalid")
    collected = datetime.now(UTC)
    op = str(step["op"])
    provenance = Provenance(
        "fixed_read_only_rcon", collected, "server=current;permissions", complete=True
    )
    if op == "list_admins":
        admins = row.get("admins", [])
        if not isinstance(admins, list):
            raise AuthoritativeFactError("admin list is invalid")
        connected_only = step.get("connected_only") is True
        summary = (
            "Currently connected Factorio administrators: " if connected_only
            else "Players with the current Factorio administrator flag: "
        ) + (
            ", ".join(map(str, admins)) if admins else "none"
        ) + ". These are Factorio admin flags, not server ownership."
        return ToolResult(
            ResultStatus.COMPLETE, summary, provenance,
            {"operation": op, "admins": admins, "connected_only": connected_only,
             "role_scope": "Factorio admin flags only"},
        )
    requested = str(step["player"])
    if row.get("found") is not True:
        return ToolResult(
            ResultStatus.UNKNOWN,
            f"Factorio has no current player record matching {requested}.",
            provenance, {"operation": op, "player": requested, "found": False},
        )
    action = row.get("action")
    if action and row.get("action_known") is not True:
        summary = f"Factorio does not expose an input action named {action}."
        status = ResultStatus.UNKNOWN
    elif action:
        summary = (
            f"{row['player']} is {'allowed' if row.get('allowed') else 'not allowed'} to "
            f"perform {action}; admin={str(bool(row.get('admin'))).lower()}, "
            f"permission group={row.get('group', 'unknown')}, Factorio input action="
            f"{row.get('input_action', action)}."
        )
        status = ResultStatus.COMPLETE
    else:
        denied = row.get("denied_actions", [])
        summary = (
            f"{row['player']}: admin={str(bool(row.get('admin'))).lower()}, permission "
            f"group={row.get('group', 'unknown')}, denied effective actions={len(denied)}."
        )
        status = ResultStatus.COMPLETE
    return ToolResult(status, summary, provenance, {"operation": op, **row})


def _lua_long_string(value: str) -> str:
    if "]]" in value or "\r" in value or "\n" in value:
        raise ValueError("player/action text cannot be represented in the fixed query")
    return "[[" + value + "]]"


def _git_revision(repository: Path) -> str:
    try:
        head = (repository / ".git" / "HEAD").read_text(encoding="ascii").strip()
        if head.startswith("ref: "):
            value = (repository / ".git" / head[5:]).read_text(encoding="ascii").strip()
        else:
            value = head
        return value[:12] if value else "unknown"
    except OSError:
        return "unknown"


def _display_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
