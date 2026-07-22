"""Playable Step 7 full-bot prototype runtime."""

from __future__ import annotations

import time
from pathlib import Path

from .archive import ArchiveRecord, TextEventArchive, redact_sensitive
from .authoritative import (
    AuthoritativeFactError,
    AuthoritativeFactProvider,
    PermissionProvider,
    direct_fact_answer,
)
from .config import FullBotConfig
from .contracts import EventKind, NormalizedEvent, ResultStatus, StateNeedsPlan, ToolResult
from .delivery import MinimalDeliveryWorker, MinimalRenderer, RconDeliveryTransport
from .ingestion import (
    DurableLogReader,
    FactorioEventNormalizer,
    LogIngestionService,
    event_from_archive_record,
    retained_log_events,
)
from .interactions import InvocationClassifier, WelcomeService
from .model import ConversationMemory, GroqModelGateway, ModelError, ModelRateLimitError
from .live_state import FixedLiveStateProvider, LiveStateError
from .freeform_rcon import FreeformRconError, FreeformRconProvider
from .platform_state import PlatformInvestigationProvider, PlatformStateError
from .logistics_state import LogisticsInvestigationProvider, LogisticsStateError
from .state_planning import StatePlanError
from .routing import MinimalConversationRouter
from .state import FlatTextStateStore


MODEL_INTERCALL_DELAY_SECONDS = 2.0


class FullBotRuntime:
    def __init__(self, config: FullBotConfig, *, model: object | None = None) -> None:
        self.config = config.validate()
        state_dir = config.runtime_dir / "full-bot-state"
        self.state = FlatTextStateStore(state_dir)
        self.archive = TextEventArchive(
            config.runtime_dir / "full-bot-archive",
            rotation_bytes=config.archive_rotation_bytes,
        )
        self.ingestion = LogIngestionService(
            DurableLogReader(config.server_log_path, self.state, start_at_end=True),
            self.archive,
            FactorioEventNormalizer(),
        )
        self.classifier = InvocationClassifier()
        self.router = MinimalConversationRouter(config)
        self.renderer = MinimalRenderer(character_limit=config.chat_character_limit)
        self.delivery = MinimalDeliveryWorker(
            transport=RconDeliveryTransport(
                wrapper_path=config.rcon_wrapper_path,
                command_path=config.rcon_command_path,
                timeout_seconds=config.rcon_timeout_seconds,
            ),
            archive=self.archive,
            state=self.state,
            enabled=config.public_replies_enabled,
        )
        self.welcomes = WelcomeService(self.state)
        self.history_events = self._seed_seen_players()
        self.memory = ConversationMemory(3)
        self.recent_observations: dict[str, tuple[ToolResult, ...]] = {}
        self.live_state = FixedLiveStateProvider(
            wrapper_path=config.rcon_wrapper_path,
            command_path=config.rcon_command_path,
            timeout_seconds=config.rcon_timeout_seconds,
        )
        self.freeform_rcon = FreeformRconProvider(
            wrapper_path=config.rcon_wrapper_path,
            command_path=config.rcon_command_path,
            timeout_seconds=config.rcon_timeout_seconds,
        )
        self.platform_state = PlatformInvestigationProvider(
            wrapper_path=config.rcon_wrapper_path,
            command_path=config.rcon_command_path,
            timeout_seconds=config.rcon_timeout_seconds,
        )
        self.logistics_state = LogisticsInvestigationProvider(
            wrapper_path=config.rcon_wrapper_path,
            command_path=config.rcon_command_path,
            timeout_seconds=config.rcon_timeout_seconds,
        )
        self.model = model or GroqModelGateway.from_key_file(
            config.api_key_path,
            model=config.model,
            timeout_seconds=config.provider_timeout_seconds,
        )
        self.authoritative = AuthoritativeFactProvider(
            config, self.archive, self.history_events, self.model,
            PermissionProvider(
                wrapper_path=config.rcon_wrapper_path,
                command_path=config.rcon_command_path,
                timeout_seconds=config.rcon_timeout_seconds,
            ),
        )

    def _seed_seen_players(self) -> tuple[NormalizedEvent, ...]:
        """Reconstruct permanent seen-player memory without sending greetings."""
        archived_events = []
        for record in self.archive.iter_records():
            if record.kind not in {
                EventKind.PUBLIC_CHAT.value,
                EventKind.PLAYER_JOIN.value,
                EventKind.PLAYER_LEAVE.value,
            }:
                continue
            try:
                archived_events.append(event_from_archive_record(record))
            except (KeyError, TypeError, ValueError):
                continue
        log_events = retained_log_events(
            self.config.server_log_path, FactorioEventNormalizer()
        )
        combined = {event.event_id: event for event in (*archived_events, *log_events)}
        events = tuple(combined.values())
        self.welcomes.seed_seen_players(events)
        return events

    def process_available(self) -> int:
        handled = 0
        for event in self.ingestion.ingest_available().events:
            if event.kind is EventKind.PLAYER_JOIN:
                intent = self.welcomes.prepare(event, enabled=self.config.welcomes_enabled)
                if intent is not None:
                    self.delivery.deliver_welcome(intent, self.renderer, self.welcomes)
                continue
            decision = self.classifier.classify(event)
            if decision is None or not decision.accepted:
                continue
            handoff = self.router.conversation_only(decision)
            if handoff is None:
                continue
            handled += 1
            history = self.memory.exchanges_for(decision.actor)
            player_key = decision.actor.casefold()
            prior_results = self.recent_observations.get(player_key, ())
            self.archive.append(ArchiveRecord.now(
                "state_plan_request", "history=" + str(len(history)) +
                ";prior_observations=" + str(len(prior_results)),
                correlation_id=handoff.plan.correlation_id, actor=decision.actor,
            ))
            planning_warning = None
            try:
                state_plan = self.model.plan_state_needs(
                    handoff.plan, history=history, prior_results=prior_results
                )
                self.archive.append(ArchiveRecord.now(
                    "state_plan_validated", "tools=" + ",".join(state_plan.tools) +
                    ";subjects=" + ",".join(state_plan.subjects) +
                    ";investigation_steps=" + str(len(state_plan.investigation_steps)) +
                    ";fact_steps=" + str(len(state_plan.fact_steps)) +
                    ";freeform_rcon=" + ("yes" if state_plan.rcon_command else "no") +
                    _model_usage_suffix(self.model),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
            except ModelRateLimitError as error:
                self.archive.append(ArchiveRecord.now(
                    "state_plan_rate_limited", redact_sensitive(str(error)),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                self._deliver_rate_limit(handoff.plan.correlation_id, decision.actor)
                continue
            except (ModelError, StatePlanError, ValueError) as error:
                self.archive.append(ArchiveRecord.now(
                    "state_plan_error", redact_sensitive(str(error)),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                fallback = self.router.route(decision)
                fallback_tool = None if fallback is None else fallback.live_query
                aliases = {"players": "get_connected_players", "research": "get_current_research",
                           "game_time": "get_game_time", "surfaces": "get_available_surfaces"}
                state_plan = StateNeedsPlan((aliases[fallback_tool],) if fallback_tool else ())
                planning_warning = ToolResult(
                    ResultStatus.UNKNOWN,
                    "The requested investigation plan was invalid; answer from prior evidence or clarify using only registered capabilities.",
                    values={"supported_investigation_domains": ["space_platforms", "logistics"]},
                    warnings=("unsupported or malformed investigation plan",),
                )
            tool_results = (planning_warning,) if planning_warning is not None else ()
            if state_plan.fact_steps:
                try:
                    fact_results = self.authoritative.execute(
                        state_plan.fact_steps, subjects=state_plan.subjects
                    )
                    tool_results = tuple(tool_results) + tuple(fact_results)
                    self.archive.append(ArchiveRecord.now(
                        "authoritative_fact_result",
                        "steps=" + str(len(state_plan.fact_steps)) +
                        ";count=" + str(len(fact_results)),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                except (AuthoritativeFactError, OSError, ValueError) as error:
                    self.archive.append(ArchiveRecord.now(
                        "authoritative_fact_error", redact_sensitive(str(error)),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                    tool_results = tuple(tool_results) + (ToolResult(
                        ResultStatus.UNAVAILABLE,
                        "The requested authoritative runtime fact is unavailable right now.",
                        warnings=("authoritative fact lookup failed",),
                    ),)
            if state_plan.tools:
                try:
                    query_started = time.monotonic()
                    tool_results = tuple(tool_results) + self.live_state.execute(state_plan.tools)
                    elapsed_ms = round((time.monotonic() - query_started) * 1000)
                    self.archive.append(ArchiveRecord.now(
                        "tool_result", "tools=" + ",".join(state_plan.tools) +
                        ";status=complete;count=" + str(len(tool_results)) +
                        ";elapsed_ms=" + str(elapsed_ms),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                except LiveStateError as error:
                    self.archive.append(ArchiveRecord.now(
                        "tool_error", redact_sensitive(str(error)),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                    response = "I couldn't retrieve the requested current server state just now."
                    rendered = self.renderer.render_reply(
                        handoff.plan.correlation_id, decision.actor, response
                    )
                    result = self.delivery.deliver(rendered)
                    if result.status is ResultStatus.COMPLETE:
                        self.memory.commit(decision.actor, decision.request_text, result.exact_text)
                    continue
            if state_plan.investigation_steps:
                grouped = {
                    domain: tuple(step for step in state_plan.investigation_steps if step.get("domain") == domain)
                    for domain in ("space_platforms", "logistics")
                }
                for domain, steps in grouped.items():
                    if not steps:
                        continue
                    try:
                        query_started = time.monotonic()
                        provider = self.platform_state if domain == "space_platforms" else self.logistics_state
                        investigation_results = provider.execute(steps)
                        elapsed_ms = round((time.monotonic() - query_started) * 1000)
                        tool_results = tuple(tool_results) + tuple(investigation_results)
                        self.archive.append(ArchiveRecord.now(
                            "investigation_result",
                            "domain=" + domain + ";steps=" + str(len(steps)) + ";count=" +
                            str(len(investigation_results)) + ";elapsed_ms=" + str(elapsed_ms),
                            correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                        ))
                    except (PlatformStateError, LogisticsStateError, ValueError) as error:
                        self.archive.append(ArchiveRecord.now(
                            "investigation_error", redact_sensitive(str(error)),
                            correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                        ))
                        tool_results = tuple(tool_results) + (ToolResult(
                            ResultStatus.UNAVAILABLE,
                            "The requested read-only investigation is unavailable right now.",
                            values={"domain": domain},
                            warnings=("live " + domain + " query failed",),
                        ),)
            if state_plan.rcon_command:
                command = state_plan.rcon_command
                self.archive.append(ArchiveRecord.now(
                    "freeform_rcon_command", redact_sensitive(command),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                try:
                    query_started = time.monotonic()
                    rcon_result = self.freeform_rcon.execute(command)
                    elapsed_ms = round((time.monotonic() - query_started) * 1000)
                    tool_results = tuple(tool_results) + (rcon_result,)
                    output = str(rcon_result.values.get("output", ""))
                    self.archive.append(ArchiveRecord.now(
                        "freeform_rcon_result",
                        "status=" + rcon_result.status.value + ";elapsed_ms=" +
                        str(elapsed_ms) + ";output=" + redact_sensitive(output),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                except FreeformRconError as error:
                    self.archive.append(ArchiveRecord.now(
                        "freeform_rcon_error", redact_sensitive(str(error)),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                    tool_results = tuple(tool_results) + (ToolResult(
                        ResultStatus.UNAVAILABLE,
                        "The model-authored live RCON query failed.",
                        warnings=("free-form RCON query failed",),
                    ),)
            if (state_plan.fact_steps and not state_plan.rcon_command and
                    not state_plan.tools and not state_plan.investigation_steps):
                response = direct_fact_answer(tool_results)
                try:
                    rendered = self.renderer.render_reply(
                        handoff.plan.correlation_id, decision.actor, response,
                    )
                except ValueError as error:
                    self.archive.append(ArchiveRecord.now(
                        "renderer_error", redact_sensitive(str(error)),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                    continue
                result = self.delivery.deliver(rendered)
                if result.status is ResultStatus.COMPLETE:
                    self.memory.commit(decision.actor, decision.request_text, result.exact_text)
                    self.recent_observations[player_key] = tuple(tool_results)
                continue
            # Planning and synthesis are the two normal hosted calls for one request.
            # Keep them from landing as a back-to-back burst against Groq's token limit.
            time.sleep(MODEL_INTERCALL_DELAY_SECONDS)
            self.archive.append(ArchiveRecord.now(
                "model_request", "route=synthesis;history=" + str(len(history)) +
                ";tool_results=" + str(len(tool_results)),
                correlation_id=handoff.plan.correlation_id, actor=decision.actor,
            ))
            try:
                trusted_context = handoff.context
                if tool_results:
                    trusted_context = trusted_context.replace(
                        "No fresh live-game snapshot was collected for this request. Do not claim "
                        "to know current players, research, map locations, inventories, production, "
                        "or other current-save facts.",
                        "Fresh live observations were collected only for the operations in the "
                        "trusted tool-results message. Treat all other current-save facts as unknown.",
                    )
                response = self.model.generate(
                    handoff.plan, history=history,
                    tool_results=tool_results or prior_results,
                    trusted_context=trusted_context,
                )
                self.archive.append(ArchiveRecord.now(
                    "model_response", "route=synthesis;characters=" + str(len(response)) +
                    _model_usage_suffix(self.model),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
            except ModelRateLimitError as error:
                self.archive.append(ArchiveRecord.now(
                    "model_rate_limited", redact_sensitive(str(error)),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                self._deliver_rate_limit(handoff.plan.correlation_id, decision.actor)
                continue
            except ModelError as error:
                self.archive.append(ArchiveRecord.now(
                    "model_error", redact_sensitive(str(error)),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                continue
            try:
                rendered = self.renderer.render_reply(
                    handoff.plan.correlation_id, decision.actor, response,
                    trusted_rich_text=_trusted_platform_names(tool_results or prior_results),
                )
            except ValueError as error:
                self.archive.append(ArchiveRecord.now(
                    "renderer_error", redact_sensitive(str(error)),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                continue
            result = self.delivery.deliver(rendered)
            if result.status is ResultStatus.COMPLETE:
                self.memory.commit(decision.actor, decision.request_text, result.exact_text)
                if tool_results:
                    self.recent_observations[player_key] = tuple(tool_results)
        return handled

    def _deliver_rate_limit(self, correlation_id: str, actor: str) -> None:
        """End this request locally after one 429; never ask Groq to explain Groq."""
        try:
            rendered = self.renderer.render_reply(
                correlation_id, actor,
                "I'm temporarily rate-limited. Please try that again in about a minute.",
            )
        except ValueError as error:
            self.archive.append(ArchiveRecord.now(
                "renderer_error", redact_sensitive(str(error)),
                correlation_id=correlation_id, actor=actor,
            ))
            return
        self.delivery.deliver(rendered)

    def run_forever(self) -> None:
        print("Jimbo full-bot prototype is watching new chat.", flush=True)
        while True:
            self.process_available()
            time.sleep(self.config.poll_interval_seconds)


def live_config() -> FullBotConfig:
    return FullBotConfig().with_overrides(
        live_log_enabled=True,
        live_rcon_enabled=True,
        public_replies_enabled=True,
        welcomes_enabled=True,
    )


def _trusted_platform_names(results: tuple[ToolResult, ...]) -> tuple[str, ...]:
    names: list[str] = []
    for result in results:
        values = result.values
        if not isinstance(values, dict) or values.get("domain") != "space_platforms":
            continue
        rows = values.get("results", ())
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("name"), str):
                names.append(row["name"])
    return tuple(dict.fromkeys(names))


def _model_usage_suffix(model: object) -> str:
    usage = getattr(model, "last_usage", {})
    limits = getattr(model, "last_rate_limits", {})
    parts = []
    if isinstance(usage, dict):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if isinstance(usage.get(key), int):
                parts.append(key + "=" + str(usage[key]))
    if isinstance(limits, dict):
        for key in ("x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens"):
            if key in limits:
                parts.append(key.replace("x-ratelimit-", "remaining_") + "=" + str(limits[key]))
    return (";" + ";".join(parts)) if parts else ""
