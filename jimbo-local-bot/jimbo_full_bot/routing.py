"""Thin conversation handoff router for the Step 6 prototype stub."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .config import FullBotConfig
from .contracts import AuthorityDecision, RequestPlan, RouteKind
from .interactions import InvocationDecision


STATIC_SERVER_CONTEXT = (
    "Server context: this multiplayer server runs Factorio 2.1.12 with the "
    "Space Age expansion and the Elevated Rails and Quality features enabled. "
    "The runtime can retrieve connected players, current research progress, "
    "game time, and available surfaces through fixed read-only queries when a "
    "request is recognized. The model cannot choose or author RCON commands. "
    "No fresh live-game snapshot was collected for this request. Do not claim "
    "to know current players, research, map locations, inventories, production, "
    "or other current-save facts."
)


@dataclass(frozen=True, slots=True)
class ConversationHandoff:
    plan: RequestPlan
    context: str
    live_query: str | None = None


LIVE_ROUTES = (
    ("players", re.compile(r"\b(?:who(?:'s| is)? (?:online|connected)|online players?|connected players?)\b", re.I)),
    ("research", re.compile(r"\b(?:current research|researching|research progress|what research)\b", re.I)),
    ("game_time", re.compile(r"\b(?:game time|save time|how long (?:has )?the (?:game|save))\b", re.I)),
    ("surfaces", re.compile(r"\b(?:surfaces?|planets?|worlds?) (?:are )?(?:available|known|unlocked)?\b", re.I)),
)


class MinimalConversationRouter:
    """Route accepted invocations to conversation without tools or RCON."""

    def __init__(self, config: FullBotConfig) -> None:
        self.config = config.validate()

    def route(self, decision: InvocationDecision) -> ConversationHandoff | None:
        if not decision.accepted:
            return None
        is_management = (
            decision.actor.casefold() == self.config.management_player.casefold()
        )
        authority = AuthorityDecision(
            actor=decision.actor,
            is_management=is_management,
            allowed=True,
            capability="conversation",
            reason="public conversation is available to players",
        )
        live_query = next(
            (name for name, pattern in LIVE_ROUTES if pattern.search(decision.request_text)),
            None,
        )
        plan = RequestPlan(
            correlation_id="request-" + decision.event_id,
            event_id=decision.event_id,
            actor=decision.actor,
            request_text=decision.request_text,
            route=RouteKind.DIRECT_LIVE_QUERY if live_query else RouteKind.CONVERSATION,
            authority=authority,
            allowed_tool_families=("fixed_live_snapshot",) if live_query else (),
        )
        return ConversationHandoff(plan=plan, context=STATIC_SERVER_CONTEXT, live_query=live_query)
