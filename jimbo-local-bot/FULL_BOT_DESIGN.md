# Jimbo Full Bot Architecture and Design

Status: proposed architecture baseline for implementation review (2026-07-21)

## 1. Purpose and design stance

This document translates `FULL_BOT_REQUIREMENTS.md` into an implementable first-release architecture. It preserves the proven public-chat loop while separating model reasoning from authority, runtime truth, rendering, delivery, and every state-changing operation.

The recommended shape is a dependency-light Python modular monolith with an append-only UTF-8 text event archive and small atomic flat-text state files. Query indexes are rebuilt in memory from the archive where needed. JSON and SQLite are not first-release storage dependencies and should be considered only if later evidence demonstrates a concrete need. A single deployable process keeps operations appropriate for one Factorio server; strong module boundaries, typed contracts, and separate execution queues preserve a future path to split services without introducing distributed-system cost now.

The architecture follows five rules:

1. Application code owns authority, policy, runtime truth, and final rendering.
2. Model output is untrusted text or a proposed typed plan, never permission.
3. Read-only investigation and ghost placement use different schemas, validators, executors, queues, and audit records.
4. Unknown, stale, partial, and failed are first-class result states.
5. Only a successfully delivered player-visible exchange enters conversational memory.

## 2. Context and boundaries

### 2.1 Actors and dependencies

- Players invoke Jimbo in public chat and may use enabled read-only capabilities.
- `dlbattle` is the sole case-insensitive in-chat management identity.
- The operator controls local deployment, configuration, credentials, health, and maintenance modes.
- The model provider supplies language generation and investigation planning, but has no authority and is not a runtime source of truth.
- Factorio supplies the append-only console log and live game state through the existing fixed RCON credential path.

### 2.2 System context

```text
Factorio server-console.log
        |
        v
 Event Ingestor -> Canonical Archive -> Router/Policy -> Conversation Orchestrator
                                           |                    |
                                           |              Model Gateway
                                           |                    |
                      +--------------------+--------------------+
                      |                                         |
             Read-only Investigation                    Ghost Placement
             planner + safe executor              management-only pipeline
                      |                                         |
                      +--------------------+--------------------+
                                           |
                                  Trusted Renderer
                                           |
                                  Delivery Queue/RCON
                                           |
                                      Factorio chat
```

There is no general command executor. The only component allowed to submit world-changing RCON is the dedicated ghost-placement executor after management authorization and placement validation.

## 3. Logical architecture

### 3.1 Event ingestor and durable cursor

The ingestor tails the Factorio console log in binary mode, reconstructs complete lines, and normalizes supported records into typed events. It stores source identity, byte offset, a content-derived event ID, and rotation/truncation observations transactionally with archive append intent. On restart it resumes from the durable cursor and processes records written while stopped.

Event identity is `sha256(source_instance || byte_start || byte_end || raw_record)`. A source instance is derived from canonical path plus observed file identity and creation metadata where available. If truncation or replacement is detected, the ingestor creates a new source instance rather than rewinding the old one. The event store enforces uniqueness on event ID, preventing duplicate replies and greetings.

Supported normalized event types are `public_chat`, `player_join`, `player_leave`, and optional reliably parsed server events. Malformed and incomplete lines are archived as diagnostic ingestion outcomes when safe, but never routed as player requests.

### 3.2 Canonical archive

The canonical archive is an append-only UTF-8 text log. The initial policy rotates the active segment before it would exceed 10 MB and retains every numbered segment; no archive segment is deleted. Each physical line is one escaped record using a minimal documented tagged format, for example `version<TAB>timestamp<TAB>kind<TAB>event-id<TAB>correlation-id<TAB>actor<TAB>payload`. Tabs, newlines, backslashes, and control characters in values are escaped deterministically. Record kinds cover source chat/join/leave lines, routing decisions, tool observations and provenance, model output, rendered output, delivery outcomes, errors, and placement activity. The payload may remain readable labeled text; it does not need to be JSON.

The append-only text archive remains the self-contained record of truth. Small versioned flat-text files hold mutable operational state such as cursors, seen players, preferences, delivery deduplication, runtime flags, and placement progress. These files use a documented line-oriented key/value or tabular format. Each update uses write-to-temporary-file, flush, and atomic replace. Query indexes are derived in memory from the archive or state files. Archive writes are flushed before an event is acknowledged as consumed. Secrets and full hidden prompts are excluded by construction.

### 3.3 Router and policy engine

The router remains deterministic for invocation, authority, preference commands,
placement requests, prohibited actions, and runtime-owned facts. For ordinary
informational requests, a bounded model planning pass decides whether fresh
game state is needed and may propose only registered read-only operations. It
produces a typed `RequestPlan` with one route:

- `direct_runtime_fact` for identity, limits, provider, health, and configuration;
- `direct_archive_query` for joins, leaves, and previously-seen questions;
- `direct_live_query` for simple current state such as online players or research;
- `calculation` for ratios, throughput, crafting, modules, power, and furnaces;
- `investigation` for multi-step live-state questions;
- `conversation` for generic Factorio or harmless general conversation;
- `preference_command` for inspect/set/reset;
- `ghost_design` or `ghost_place` for the dedicated placement workflow;
- `decline` for unsupported or unauthorized actions.

Before orchestration, the policy engine attaches an application-owned authority
decision, artifact/output restrictions, allowed tool families, maximum planning
passes, and chat budget. The model cannot widen these fields. A model proposal
is data, not permission: local code rejects unknown operations or arguments and
maps accepted operations to locally authored read-only RCON implementations.
Direct runtime and policy facts remain application-rendered. Live observations
may be synthesized by the model only after their values, freshness, status, and
provenance are supplied as trusted tool results.

### 3.4 Conversation orchestrator

The orchestrator owns one correlation ID from accepted invocation through
delivery. It loads the last three completed exchanges for the requesting
player, applies deterministic preferences, and performs at most one
state-needs planning pass. A strict plan such as
`{"tools":["get_connected_players"]}` is locally parsed and validated. If the
plan contains approved tools, the orchestrator executes them through the serial
read-only RCON path, then makes one answer pass with trusted results and
provenance. If no tool is requested, it proceeds directly to the answer pass.
There is no recursive tool loop.

The initial planner allowlist is `get_connected_players`,
`get_current_research`, `get_game_time`, and `get_available_surfaces`. The
current deterministic phrase matcher remains a temporary prototype fallback
during rollout, not the intended final state-needs decision mechanism.

Per-player history is an in-memory ring of completed exchanges. It is intentionally not restored after restart. The durable archive is not silently reused as conversational memory. A history entry is committed only after the delivery worker records a successful public reply. Provider failures, rejected renders, ignored messages, drafts, and failed deliveries do not enter history.

### 3.5 Model gateway

The gateway exposes a provider-neutral interface and retains Groq `openai/gpt-oss-120b` as the initial deployment. Configuration identifies the provider and model; there is no automatic Ollama fallback. The gateway enforces timeouts, bounded context/output, structured-output schemas where used, retry policy, cancellation, and redaction of secrets.

Prompts separate trusted application facts, untrusted player text, recent conversation, and tool results. Tool results carry provenance and completeness. The gateway never receives RCON credentials and never directly calls Factorio, files, or the network beyond the configured model API.

## 4. Read-only investigation subsystem

### 4.1 Query model

The first slice exposes four argument-free registered operations for connected
players, current research, game time, and available surfaces. The model chooses
zero or more of those operations through a strict structured plan; local code
validates the names, maximum count, and absence of extra fields before any RCON
call. Unknown or malformed proposals execute nothing.

Broader live-state access is implemented as a small safe query language rather
than one command per anticipated question. The model may later propose a JSON
investigation plan containing only registered operations and typed arguments:

```json
{
  "steps": [
    {"op": "find_entities", "scope": {"surface": "aquilo"},
     "where": [{"field": "type", "eq": "logistic-container"}],
     "select": ["unit_number", "name", "position", "request_slots"],
     "limit": 200},
    {"op": "filter", "input": 0,
     "where": [{"field": "request_slots.item", "eq": "quantum-processor"}]}
  ]
}
```

Registered primitives cover discovery, filtering, projection, counting, grouping, aggregation, and relationship traversal. Domain adapters expose surfaces/planets, forces, players, entities/ghosts, inventories and settings, logistics, trains, platforms, electric networks, statistics, pollution, resources, research, and positions where the Factorio API makes them observable.

### 4.2 Safety and execution

The plan validator rejects unknown operations/fields, mutation-shaped APIs, arbitrary code, excessive limits, unbounded scans, invalid prototypes, and unsupported cross-domain joins. Local code compiles an accepted plan into predefined read-only Lua templates. Templates return compact JSON through `rcon.print` and have explicit surface/force scope, maximum visited objects, maximum result bytes, and execution deadline.

Large work is paginated or aggregated server-side in bounded increments. The executor uses a dedicated serial queue so investigations cannot overwhelm the server. Each result reports `complete`, `partial`, `timeout`, `unavailable`, or `stale`, plus collection time, scope, filters, counts, object identities, and warnings. The synthesizer must preserve those qualifiers.

### 4.3 Deterministic calculations

Calculations use a versioned local data model and explicit input schema. Inputs include recipe/item, quality, machine, crafting speed, modules/beacons, belt throughput, game version, and the requested comparison metric. Missing material inputs yield a clarification rather than guessed defaults. Output contains assumptions, formula inputs, result units, rounding method, and source version.

## 5. Ghost and blueprint placement subsystem

### 5.1 State machine

Placement is a management-only, explicitly staged workflow:

```text
DISCUSS -> DRAFT -> VALIDATED -> MARKER_TEST -> AWAIT_LOCATION_CONFIRMATION
        -> PREFLIGHT -> BATCH_PLACE -> AUDIT -> COMPLETE
                         |              |
                         +-> ABORTED <--+
```

Discussion and design requests from ordinary players may produce non-executable design advice, but only a request whose authenticated chat actor is `dlbattle` can enter `VALIDATED` or later. Authority is rechecked at every transition that can mutate the world.

### 5.2 Structured design contract

The preferred contract is a `GhostDesign` document containing Factorio version, surface, exact anchor, entity prototypes, center positions, directions, qualities, recipes, recipe qualities, filters, priorities, control behavior, wire connections, module requests, and design provenance. Blueprint input must decode, validate, and round-trip before conversion into this structure. Duplicate centers, unknown prototypes, invalid directions, out-of-bounds positions, and unsupported settings fail validation.

Raw model-authored Lua/RCON is disabled by default. If later enabled, it is accepted only as an input language to the placement parser and must reduce to the same `GhostDesign` allowlist; text that cannot be proven equivalent is rejected. It never enters a general executor.

### 5.3 Preflight and incremental execution

The system first establishes a distinctive exact marker and reports its GPS coordinate. A representative ghost for every involved prototype is validated, placed in a tiny batch, and audited. The operator/player must confirm the location before material placement.

Preflight scans the complete footprint for tiles, rails, entities, water, and collision. `surface.can_place_entity` is evaluated for every planned entity; failure aborts the entire placement before the main batches. Large placements are divided into small bounded batches with a response and audit after every batch. Timeout means unknown execution state: the pipeline stops and audits before any retry.

Final audit compares every expected prototype and center position and verifies settings that granular ghosts may lose. Cleanup is a separate management-authorized plan derived from the original expected-position set and limited to matching prototypes; it never removes unrelated entities, rails, or player markers.

## 6. Rendering and delivery

The response renderer accepts structured content, not arbitrary rich text. Dynamic model/player text is escaped and normalized separately from trusted locally constructed tokens such as validated GPS links. It removes unsupported Markdown and control characters, collapses line breaks, protects commands/coordinates/names from preference transforms, and measures the final encoded byte length against the configured Factorio chat budget.

Oversized prose is summarized or deliberately paginated. Opaque artifacts are never truncated: they are delivered only if a deterministic generator produced them, validation passed, and the complete artifact fits. Otherwise Jimbo declines with a useful explanation. Command-shaped, Lua, RCON, shell, encoded-payload, and blueprint-like output is detected on initial and follow-up turns.

The delivery queue serializes public output, applies timeout/backoff, records the exact sent text and RCON result, and detects self-authored chat records. Delivery failure is visible to operations and prevents memory commit.

## 7. Welcomes, preferences, and social behavior

Join events bypass invocation but not deduplication or maintenance controls. A deterministic template chooses `Welcome, <name>! Begin queries with Jimbo.` for first seen and `Welcome back, <name>! Begin queries with Jimbo.` for a durably seen player. The wording may be refined, but every template must retain the explicit `Jimbo` invocation instruction and remain compatible with the supported `Hey Jimbo` form. Seen identity is keyed by casefolded name and retains latest display spelling, first-seen time, and last-seen time. No model call is made and no history detail is disclosed. Operators can disable or temporarily suppress greetings.

Durable preferences use an allowlisted schema initially containing `response_mode` (`facts_only` or `facts_and_advice`) and approved presentation transforms. Only the affected player may set, inspect, reset, or edit their preferences. Application code applies transforms after factual rendering with protected spans and a readable fallback.

Social prompts remain model-handled within PG-13 behavior. The application blocks impersonation, unattributed relays, targeted harassment, private-history disclosure, and unsafe actions. Presence never implies AFK state, availability, consent, or willingness to perform work.

## 8. Data design

Logical flat-file state records:

- `source_cursors(source_instance, path, byte_offset, last_event_id, updated_at)`
- `events(event_id, archive_segment, archive_offset, kind, actor_key, occurred_at, correlation_id)`
- `seen_players(player_key, display_name, first_seen_at, last_seen_at)`
- `preferences(player_key, schema_version, response_mode, transforms_json, updated_at)`
- `deliveries(delivery_id, correlation_id, status, attempt_count, rendered_hash, completed_at)`
- `placement_runs(run_id, requester_key, state, design_hash, surface, anchor_json, created_at, updated_at)`
- `placement_batches(run_id, batch_no, expected_json, status, audit_json)`
- `runtime_flags(name, value_json, updated_at)`

All timestamps are UTC ISO 8601. File formats are versioned and migrated forward with a backup plus startup integrity check. Mutable text state uses write-to-temporary-file, flush, and atomic replace; indexes that can be reconstructed from the archive are not persisted. Credentials remain in existing ignored runtime locations and are referenced only by path/config key.

## 9. Concurrency, failure, and observability

The listener stays responsive by separating ingestion from bounded work queues. Per-player invocation ordering is preserved; different players may wait concurrently on provider calls. Read-only RCON uses a serial bounded queue, delivery uses a serial queue, and placement has an exclusive mutation lease. Queue admission limits produce a friendly busy response rather than unbounded memory growth.

Every external call has a timeout and classified outcome. One failed event cannot terminate ingestion. Retries are limited to idempotent operations; world-changing placement is never blindly retried. Health reports cover log freshness, cursor lag, archive writes, queue depth, provider status, RCON status, renderer rejections, delivery failures, and active placement state. Metrics remain local and must not disclose public cost/quota details.

## 10. Deployment and operator controls

Implementation, staging, smoke validation, and public activation are separate gates. The existing fixed project launcher remains the operational entry point and should gain narrowly scoped actions through its validated action file only when implementation reaches them. Required controls include status, start, stop, restart, public replies on/off, welcomes on/off/suppress, queue drain, health summary, and placement abort.

Recommended rollout:

1. Build archive, ingestion, deterministic direct answers, renderer, and delivery behind public-output disabled mode.
2. Add isolated per-player memory, provider gateway, preferences, and welcomes; validate using recorded fixtures.
3. Add the calculation engine and a small set of read-only query primitives, then expand domains through adapter contracts.
4. Run staged live read-only smoke tests with harmless bounded queries.
5. Build ghost placement independently, beginning with offline validation and one representative marker ghost.
6. Complete authority, collision, batching, timeout/audit, and cleanup tests before management-only live activation.
7. Enable public replies only after acceptance scenarios pass and rollback controls are rehearsed.

Rollback stops new admission, drains or cancels non-mutating work, leaves the archive intact, and never auto-cleans partially placed ghosts. A partial placement is audited and resolved through a separately authorized recovery plan.

## 11. Test strategy and acceptance

Routine tests mock the provider and RCON. Contract tests validate schemas, prompt boundaries, query compilation, renderer encoding, archive replay, and provider replacement. Property/fuzz tests cover log fragments, rotations, invocation variants, Unicode, rich-text escaping, command-shaped output, bounded query plans, and placement coordinates.

Requirement-level tests must include:

- replay after stop/restart, truncation, and rotation without duplicate reply or greeting, with every delivered welcome and welcome-back message instructing the player to begin queries with `Jimbo`;
- authority spoofing, admin-status irrelevance, ordinary-player placement attempts, and authority recheck;
- direct runtime/live/archive answers that cannot be contradicted by the model;
- unknown/stale/partial tool outcomes and multi-step investigation provenance;
- three completed exchanges per player with failure/delivery exclusions;
- preference ownership, reset, protected factual spans, and readable fallback;
- artifact round-trip validation, command-shaped follow-ups, and Unicode byte budgets;
- marker, collision, representative prototype, small-batch, timeout audit, exact-position audit, and scoped cleanup placement cases;
- queue isolation, failure containment, and provider/RCON timeouts.

The 25 scenarios in `FULL_BOT_REQUIREMENTS.md` remain the initial end-to-end acceptance suite. Each implementation increment must map tests to stable requirement IDs.

## 12. Key decisions and deferred choices

Decisions fixed by this design:

- Python modular monolith, append-only UTF-8 text archive, small atomic flat-text state files, and rebuilt in-memory indexes; no first-release JSON or SQLite storage dependency.
- Groq provider initially, behind a replaceable gateway, with no automatic Ollama fallback.
- Deterministic-first routing and direct authoritative answers.
- Structured, bounded read-only query plans compiled to trusted templates.
- A separate management-only structured ghost-placement state machine.
- Ephemeral three-exchange per-player conversation memory.
- Application-owned rendering, preferences, welcomes, authority, and self-description.

Choices intentionally deferred until implementation evidence is available:

- Archive maintenance tooling beyond retained 10 MB numbered segments.
- The initial breadth and pagination size of each read-only domain adapter.
- Whether any raw model-authored placement language is ever worth enabling; default remains disabled.
- Exact chat byte budget and safe pagination count, which must be measured against the deployed server path.
- Whether concurrency beyond one provider request at a time improves experience without harming ordering or quota behavior.

## 13. Requirement traceability

| Requirement groups | Primary design sections |
|---|---|
| AUTH, SOC | 3.3, 5, 7 |
| EVT, WELCOME | 3.1, 7, 8 |
| ROUTE, SELF | 3.3-3.5, 6 |
| KNOW | 4.3 |
| STATE | 4.1-4.2 |
| CONV, PREF | 3.4, 7 |
| ART, RENDER | 5.2, 6 |
| GHOST | 5.1-5.3 |
| OPS, QUAL | 9-11 |
| ARCH | 3.2, 8 |

This traceability is architectural rather than a substitute for requirement-by-requirement implementation and test mapping.
