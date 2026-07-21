"""Playable Step 7 full-bot prototype runtime."""

from __future__ import annotations

import time
from pathlib import Path

from .archive import ArchiveRecord, TextEventArchive, redact_sensitive
from .config import FullBotConfig
from .contracts import EventKind, ResultStatus
from .delivery import MinimalDeliveryWorker, MinimalRenderer, RconDeliveryTransport
from .ingestion import DurableLogReader, FactorioEventNormalizer, LogIngestionService
from .interactions import InvocationClassifier, WelcomeService
from .model import ConversationMemory, GroqModelGateway, ModelError
from .live_state import FixedLiveStateProvider, LiveStateError
from .routing import MinimalConversationRouter
from .state import FlatTextStateStore


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
        self.memory = ConversationMemory(3)
        self.live_state = FixedLiveStateProvider(
            wrapper_path=config.rcon_wrapper_path,
            command_path=config.rcon_command_path,
            timeout_seconds=config.rcon_timeout_seconds,
        )
        self.model = model or GroqModelGateway.from_key_file(
            config.api_key_path,
            model=config.model,
            timeout_seconds=config.provider_timeout_seconds,
        )

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
            handoff = self.router.route(decision)
            if handoff is None:
                continue
            handled += 1
            history = self.memory.exchanges_for(decision.actor)
            if handoff.live_query is not None:
                try:
                    snapshot = self.live_state.collect()
                    response = snapshot.answer(handoff.live_query)
                    self.archive.append(ArchiveRecord.now(
                        "tool_result", "tool=fixed_live_snapshot;query=" + handoff.live_query,
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                except LiveStateError as error:
                    response = "I couldn't retrieve current server state just now."
                    self.archive.append(ArchiveRecord.now(
                        "tool_error", redact_sensitive(str(error)),
                        correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                    ))
                rendered = self.renderer.render_reply(
                    handoff.plan.correlation_id, decision.actor, response
                )
                result = self.delivery.deliver(rendered)
                if result.status is ResultStatus.COMPLETE:
                    self.memory.commit(decision.actor, decision.request_text, result.exact_text)
                continue
            self.archive.append(ArchiveRecord.now(
                "model_request", "route=conversation;history=" + str(len(history)),
                correlation_id=handoff.plan.correlation_id, actor=decision.actor,
            ))
            try:
                response = self.model.generate(
                    handoff.plan, history=history, trusted_context=handoff.context
                )
            except ModelError as error:
                self.archive.append(ArchiveRecord.now(
                    "model_error", redact_sensitive(str(error)),
                    correlation_id=handoff.plan.correlation_id, actor=decision.actor,
                ))
                continue
            try:
                rendered = self.renderer.render_reply(
                    handoff.plan.correlation_id, decision.actor, response
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
        return handled

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
