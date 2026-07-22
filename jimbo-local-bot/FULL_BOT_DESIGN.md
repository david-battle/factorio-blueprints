# Jimbo Full Bot Architecture and Design

Status: proposed architecture baseline for implementation review (2026-07-21)

## 1. Purpose and design stance

This document translates `FULL_BOT_REQUIREMENTS.md` into an implementable first-release architecture. It preserves the proven public-chat loop while separating model reasoning from authority, runtime truth, rendering, delivery, and every state-changing operation.

The recommended shape is a dependency-light Python modular monolith with an append-only UTF-8 text event archive and small atomic flat-text state files. Query indexes are rebuilt in memory from the archive where needed. JSON and SQLite are not first-release storage dependencies and should be considered only if later evidence demonstrates a concrete need. A single deployable process keeps operations appropriate for one Factorio server; strong module boundaries, typed contracts, and separate execution queues preserve a future path to split services without introducing distributed-system cost now.

The architecture follows five rules:

1. Application code owns technical capability authorization, runtime truth, and
   transport rendering; it does not own social or behavioral policy.
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
 Event Ingestor -> Canonical Archive -> Capability Router -> Conversation Orchestrator
                                           |                    |
                                           |              Model Gateway
                                           |                    |
                      +--------------------+--------------------+
                      |                                         |
             Read-only Investigation                    Ghost Placement
             planner + safe executor               player-request pipeline
                      |                                         |
                      +--------------------+--------------------+
                                           |
                                  Trusted Renderer
                                           |
                                  Delivery Queue/RCON
                                           |
                                      Factorio chat
```

The live execution path may run model-authored Lua/RCON for investigations and
supported player-equivalent actions after lightweight practical checks. Ghost
placement does not require management status. Direct entity/tile construction,
direct removal, direct tile placement, and dedicated combat automation are not
product features.

## 3. Logical architecture

### 3.1 Event ingestor and durable cursor

The ingestor tails the Factorio console log in binary mode, reconstructs complete lines, and normalizes supported records into typed events. It stores source identity, byte offset, a content-derived event ID, and rotation/truncation observations transactionally with archive append intent. On restart it resumes from the durable cursor and processes records written while stopped.

Event identity is `sha256(source_instance || byte_start || byte_end || raw_record)`. A source instance is derived from canonical path plus observed file identity and creation metadata where available. If truncation or replacement is detected, the ingestor creates a new source instance rather than rewinding the old one. The event store enforces uniqueness on event ID, preventing duplicate replies and greetings.

Supported normalized event types are `public_chat`, `player_join`, `player_leave`, and optional reliably parsed server events. Malformed and incomplete lines are archived as diagnostic ingestion outcomes when safe, but never routed as player requests.

### 3.2 Canonical archive

The canonical archive is an append-only UTF-8 text log. The initial policy rotates the active segment before it would exceed 10 MB and retains every numbered segment; no archive segment is deleted. Each physical line is one escaped record using a minimal documented tagged format, for example `version<TAB>timestamp<TAB>kind<TAB>event-id<TAB>correlation-id<TAB>actor<TAB>payload`. Tabs, newlines, backslashes, and control characters in values are escaped deterministically. Record kinds cover source chat/join/leave lines, routing decisions, tool observations and provenance, model output, rendered output, delivery outcomes, errors, and placement activity. The payload may remain readable labeled text; it does not need to be JSON.

The append-only text archive remains the self-contained record of truth. Small versioned flat-text files hold mutable operational state such as cursors, seen players, preferences, delivery deduplication, runtime flags, and placement progress. These files use a documented line-oriented key/value or tabular format. Each update uses write-to-temporary-file, flush, and atomic replace. Query indexes are derived in memory from the archive or state files. Archive writes are flushed before an event is acknowledged as consumed. Secrets and full hidden prompts are excluded by construction.

### 3.3 Capability router

The router remains deterministic only where application-owned enforcement is
required: invocation, authenticated actor identity, authority, configured
capability boundaries, and runtime-owned facts. The model interprets preference
requests, calculations, investigations, placement discussions, ambiguity, and
ordinary conversation by proposing typed plans. Local code validates those
plans and enforces ownership and configured capability authorization; it does not maintain a
parallel semantic intent classifier. A typed `RequestPlan` selects one route:

- `direct_runtime_fact` for identity, limits, provider, health, and configuration;
- `direct_archive_query` for joins, leaves, and previously-seen questions;
- `direct_live_query` for simple current state such as online players or research;
- `calculation` for ratios, throughput, crafting, modules, power, and furnaces;
- `investigation` for multi-step live-state questions;
- `conversation` for generic Factorio or general conversation;
- `preference_command` for inspect/set/reset;
- `ghost_design` or `ghost_place` for the dedicated placement workflow;
- `decline` for technically unsupported or unauthorized operations, not speech.

Before orchestration, the capability router attaches an application-owned
authorization decision, allowed tool families, maximum planning passes, and
chat budget. It does not attach acceptable-content rules. The model cannot widen
technical execution fields. A model proposal
is data, not permission: local code rejects unknown operations or arguments and
maps accepted operations to locally authored read-only RCON implementations.
Direct runtime and policy facts remain application-rendered. Live observations
may be synthesized by the model only after their values, freshness, status, and
provenance are supplied as trusted tool results.

### 3.4 Conversation orchestrator

The orchestrator owns one correlation ID from accepted invocation through
delivery. It loads the last three completed exchanges and explicit stored
preferences for the requesting player, then performs one state-needs planning
pass. A strict plan such as
`{"tools":["get_connected_players"]}` is locally parsed and validated. If the
plan contains approved tools, the orchestrator executes them through the serial
read-only RCON path, then makes one answer pass with trusted results and
provenance. If no tool is requested, it proceeds directly to the answer pass.
There is no recursive tool loop. If the planner's structured output fails local
schema validation, the gateway may make exactly one correction attempt using
the validation error; no RCON executes for either rejected plan.

The initial planner allowlist is `get_connected_players`,
`get_current_research`, `get_game_time`, and `get_available_surfaces`. The
current deterministic phrase matcher remains a temporary prototype fallback
during rollout, not the intended final state-needs decision mechanism.

Per-player history is an in-memory ring of completed exchanges. It is intentionally not restored after restart. The durable archive is not silently reused as conversational memory. A history entry is committed only after the delivery worker records a successful public reply. Provider failures, rejected renders, ignored messages, drafts, and failed deliveries do not enter history.

### 3.5 Model gateway

The gateway exposes a provider-neutral interface and retains Groq `openai/gpt-oss-120b` as the initial deployment. Configuration identifies the provider and model; there is no automatic Ollama fallback. The gateway enforces timeouts, bounded context/output, structured-output schemas where used, retry policy, cancellation, and redaction of secrets.

Prompts separate trusted application facts, untrusted player text, recent conversation, and tool results. Tool results carry provenance and completeness. The gateway never receives RCON credentials and never directly calls Factorio, files, or the network beyond the configured model API.

Model-visible state is separately bounded from RCON transport. Prior structured
observations are mechanically compacted to identity, position, location, and
requested count fields within 8,000 characters. Current tool data is supplied
in full only within 16,000 characters; beyond that, the model receives
provenance, summaries, warnings, and an explicit omission notice. Provider
token usage and non-secret remaining request/token quota headers are retained
in the local archive when available so limits can be tuned from evidence.

### 3.6 Runtime and server fact provider

A small application-owned fact provider supplies Jimbo's actual provider/model,
deployed revision, enabled capabilities, data sources, memory/restart behavior,
context/output limits, renderer behavior, and available token/quota telemetry.
It also loads human-authored server identity facts: owner/management contact,
server purpose/philosophy, and any distinct moderator roster. These facts are
versioned configuration, not model recollection.

Live Factorio administration remains a separate observation domain exposing
current admin flags, permission groups, memberships, and effective permissions
where available. Archive-derived promotion/demotion history is a third source.
Every answer labels which source it used so `in charge`, `admin`, `moderator`,
and `has permission` do not collapse into one invented role.

## 4. Read-only investigation subsystem

### 4.1 Query model

The first slice exposes four argument-free registered operations for connected
players, current research, game time, and available surfaces. The model chooses
zero or more of those operations through a strict structured plan; local code
validates the names, maximum count, and absence of extra fields before any RCON
call. Unknown or malformed proposals execute nothing.

This first slice is deployed. Natural-language intent, compound questions, and
provenance follow-ups are model-owned. Local application code is deliberately
limited to schema and allowlist validation, fixed read-only execution, result
provenance, and safety boundaries. The former phrase matcher is rollout fallback
only and must not grow into a parallel local intent-classification system.

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

The first broader vertical slice is space platforms. Live player testing showed
that the current surface list exposes an internal platform surface identifier
such as `platform-1`, which is not sufficient proof of the platform's displayed
name or its cargo. The platform adapter therefore keeps stable object identity,
display name, internal surface identity, location/status, schedule, hub cargo,
and logistic requests as distinct fields where Factorio exposes them. It must
support model-planned questions about platform identity, location, inventory,
requests, and routes without treating a surface name as a display name.

The planner receives an application-owned capability catalog describing the
registered domains, operations, arguments, output fields, relationships, and
known limitations. Capability/schema questions are answered from this catalog,
not invented by the model and not discovered through arbitrary Lua reflection.
The initial broader plan shape is intentionally small:

```json
{
  "steps": [
    {"op": "list_objects", "domain": "space_platforms",
     "select": ["id", "name", "surface", "location", "status"]},
    {"op": "inspect_inventory", "input": 0,
     "item": "space-science-pack"}
  ]
}
```

This schema is extended only through registered typed operations and fields.
The model interprets the question and proposes the plan; local code does not
maintain a question taxonomy or semantic regex catalog.

The target interface should not become a large proprietary DSL whose catalog
must be repeatedly taught to the model. The next Step 10 expansion will allow
the model to author familiar Factorio Lua/RCON directly for investigations and
supported player-equivalent actions. Local code applies lightweight command-
framing, obvious-truncation, size/time, and explicit product-boundary checks,
then attempts the command and observes the result. It does not require a
restricted AST or proof of perfect well-formedness. The current registered
operations remain the stable fallback.

Practical byte/time bounds protect transport and keep failures observable. The
model decides when a request goes too far; local code does not replace that
judgment with a rigid behavior or mutation classifier. Occasional permissive
leakage is an accepted tradeoff, and additional restrictions are added only when
explicitly requested from observed need.

The deployed logistics slice also exposes targeted exact-item counts for all
network members, providers, or storage, plus exact-item container inspection.
These operations aggregate or scope inside the trusted Factorio template before
returning rows. They answer broad quantity questions without dumping every
network inventory or relying on local language heuristics.

Player inventory inspection is intentionally broad: Jimbo may inspect every
player's inventories and personal logistic requests so players can trace items
that moved through shared logistics. No cross-player privacy filter is planned.

### 4.2 Lightweight review and execution

Registered plans retain schema validation and trusted templates. Direct model-
authored Lua/RCON receives lightweight checks for complete framing, obvious
truncation, practical size/time limits, and the explicit construction boundary:
ghosts rather than direct entity/tile construction, deconstruction orders rather
than direct removal, and no direct tile placement. Map pings/tags are supported.
The current 200 KB result ceiling protects RCON transport and parsing; the smaller
model-context budget independently protects provider quota.

Large work is paginated or aggregated server-side in bounded increments. The executor uses a dedicated serial queue so investigations cannot overwhelm the server. Each result reports `complete`, `partial`, `timeout`, `unavailable`, or `stale`, plus collection time, scope, filters, counts, object identities, and warnings. The synthesizer must preserve those qualifiers.

The latest successfully delivered structured investigation remains available
as bounded per-player working context so the model can resolve references such
as `which one`, `what is its real name`, and `how do you know`. Application code
stores and supplies the result but does not interpret the follow-up locally.

### 4.3 Deterministic calculations

Calculations use a versioned local data model and explicit input schema. Inputs include recipe/item, quality, machine, crafting speed, modules/beacons, belt throughput, game version, and the requested comparison metric. Missing material inputs produce structured validator feedback from which the model asks a clarification rather than guessing defaults. Output contains assumptions, formula inputs, result units, rounding method, and source version.

The model decides when calculation is appropriate, resolves conversational
terminology, proposes typed calculator inputs and comparison dimensions, and
asks any clarification. Local code performs only authoritative prototype/unit
validation and deterministic arithmetic. Missing or ambiguous inputs are
returned to the model as structured candidates or missing fields; local code
does not interpret natural language, decide what `best` means, or compose the
clarification itself.

## 5. Ghost and blueprint placement subsystem

### 5.1 State machine

Placement is available to every player through an explicitly staged workflow:

```text
DISCUSS -> DRAFT -> VALIDATED -> MARKER_TEST -> AWAIT_LOCATION_CONFIRMATION
        -> PREFLIGHT -> BATCH_PLACE -> AUDIT -> COMPLETE
                         |              |
                         +-> ABORTED <--+
```

Every authenticated chat player may take a placement request through `VALIDATED`
and later states. The requester identity is retained for attribution and
conversation continuity, not used as an authorization gate.

### 5.2 Structured design contract

The preferred contract is a `GhostDesign` document containing Factorio version, surface, exact anchor, entity prototypes, center positions, directions, qualities, recipes, recipe qualities, filters, priorities, control behavior, wire connections, module requests, and design provenance. Blueprint text may also be generated or displayed subject only to the ordinary message-length path. Decode what is needed when attempting placement and report Factorio's observed result.

Model-authored Lua/RCON is allowed. Lightweight checks aim to catch obvious
truncation, likely syntax/API mistakes, direct construction/removal, and direct
tile placement; uncertain cases lean toward attempting and observing.

### 5.3 Preflight and incremental execution

The system first establishes a distinctive exact marker and reports its GPS coordinate. A representative ghost for every involved prototype is validated, placed in a tiny batch, and audited. The operator/player must confirm the location before material placement.

Preflight scans the complete footprint for tiles, rails, entities, water, and collision. `surface.can_place_entity` is evaluated for every planned entity; failure aborts the entire placement before the main batches. Large placements are divided into small bounded batches with a response and audit after every batch. Timeout means unknown execution state: the pipeline stops and audits before any retry.

Final audit compares expected ghosts and settings against observed results.
Any player may request deconstruction marking for any described area or objects,
whether or not Jimbo placed them. Jimbo issues ordinary deconstruction orders;
construction bots perform the removal.

## 6. Rendering and delivery

The response renderer preserves player/model expression as far as the Factorio
chat transport permits. It normalizes only transport-breaking control characters,
line structure, encoding, and the final byte budget. Rich text and command-shaped
text may be displayed; display never routes content to Lua, RCON, shell, or slash-
command execution. Trusted structured values such as queried GPS coordinates may
still use a local renderer so Jimbo can distinguish observed data from generated
text.

Oversized prose and artifacts use the same measured chat length and pagination
behavior. No blueprint- or encoded-content-specific restriction is added.
Jimbo reports whether Factorio actually accepted an artifact, but generated text may otherwise be discussed or
displayed with an honest statement of its validation status.

The delivery queue serializes public output, applies timeout/backoff, records the exact sent text and RCON result, and detects self-authored chat records. Delivery failure is visible to operations and prevents memory commit.

## 7. Welcomes, preferences, and social behavior

Join events bypass invocation but not deduplication or maintenance controls. A deterministic template chooses `Welcome, <name>! Begin queries with Jimbo.` only when no retained server evidence has ever mentioned that player, and `Welcome back, <name>! Begin queries with Jimbo.` otherwise. Seen identity is permanent for this server, keyed by casefolded name, and retains latest display spelling, first-seen time, and last-seen time. Startup/migration seeds it from all available archived/server-log joins, leaves, and public chat without emitting historical greetings. No model call is made. Operators can disable or temporarily suppress greetings.

Durable preferences use an allowlisted schema initially containing `response_mode` (`facts_only` or `facts_and_advice`) and approved mechanical presentation transforms. Only the affected player may set, inspect, reset, or edit their preferences; application code enforces that ownership and supplies a readable fallback.

The model interprets a preference request and proposes a strict operation such
as `{"operation":"set","response_mode":"facts_only"}`. Local code checks the
authenticated owner, validates the small allowlist, and stores or returns the
value. For response modes, the model produces explicitly labeled structured
sections such as facts, assumptions, warnings, and advice; local code may omit
an explicitly tagged advice section but does not semantically classify prose.
Deterministic presentation transforms are limited to mechanical operations that
cannot alter meaning; unsupported transforms fall back to the untransformed
model response.

Social prompts, banter, role-play, and non-Factorio conversation go to the model
without an application-level moderation pass. Neither local rules nor an
auxiliary model classifies harassment, impersonation, intent, sentiment, or
acceptable behavior. Humans administer player conduct. Technical capability
checks remain separate: chat text is not executable input, and a request can use
only operations that Jimbo actually implements and that the requesting identity
is configured to invoke.

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

The listener stays responsive by separating ingestion from bounded work queues. Per-player invocation ordering is preserved; different players may wait concurrently on provider calls. Live RCON and delivery use serialized queues so attempts and outcomes remain observable. Queue admission limits produce a friendly busy response rather than unbounded memory growth.

Every external call has a timeout and classified outcome. One failed event cannot terminate ingestion. Retries are limited to idempotent operations; world-changing placement is never blindly retried. Health reports cover log freshness, cursor lag, archive writes, queue depth, provider status, RCON status, renderer rejections, delivery failures, and active placement state. Credentials remain local; public cost/quota detail follows explicit human configuration.

Operational and placement stop decisions use explicit configured signals such
as timeout, missing confirmation, measured response threshold, queue bound,
audit mismatch, or operator abort. Local code must not introduce a heuristic
notion that the server merely `seems unhealthy`. The model may summarize health
evidence but cannot determine authoritative health, rollback, or activation.

## 10. Deployment and operator controls

Implementation, staging, smoke validation, and public activation are separate gates. The existing fixed project launcher remains the operational entry point and should gain narrowly scoped actions through its validated action file only when implementation reaches them. Required controls include status, start, stop, restart, public replies on/off, welcomes on/off/suppress, queue drain, health summary, and placement abort. Every newly activated testing iteration must announce itself in public chat with a short capability/limitation summary so players know what changed and what to test.

Recommended rollout:

1. Build archive, ingestion, deterministic direct answers, renderer, and delivery behind public-output disabled mode.
2. Add isolated per-player memory, provider gateway, preferences, and welcomes; validate using recorded fixtures.
3. Add the calculation engine and a small set of read-only query primitives, then expand domains through adapter contracts.
4. Run staged live read-only smoke tests with harmless bounded queries.
5. Build ghost placement independently, beginning with offline validation and one representative marker ghost.
6. Complete player-attribution, collision, batching, timeout/audit, and cleanup tests before live activation.
7. Enable public replies only after acceptance scenarios pass and rollback controls are rehearsed.

Rollback stops new admission, drains or cancels non-mutating work, leaves the archive intact, and never auto-cleans partially placed ghosts. A partial placement is audited and resolved through a separately requested recovery plan.

## 11. Test strategy and acceptance

Routine tests mock the provider and RCON. Contract tests validate schemas, prompt boundaries, query compilation, renderer encoding, archive replay, and provider replacement. Property/fuzz tests cover log fragments, rotations, invocation variants, Unicode, rich-text transport, displayed-command non-execution, bounded query plans, and placement coordinates.

Requirement-level tests must include:

- replay after stop/restart, truncation, and rotation without duplicate reply or greeting, with every delivered welcome and welcome-back message instructing the player to begin queries with `Jimbo`;
- permanent seen-player reconstruction from chat/join/leave history, including a pre-launch chat/leave followed by a first bot-observed join receiving `Welcome back`;
- equal placement access across players, admin-status irrelevance, requester attribution, and restart continuity;
- direct runtime/live/archive answers that cannot be contradicted by the model;
- unknown/stale/partial tool outcomes and multi-step investigation provenance;
- three completed exchanges per player with failure/delivery exclusions;
- preference ownership, reset, protected factual spans, and readable fallback;
- artifact validation status, displayed-command non-execution, and Unicode byte budgets;
- marker, representative prototype, model-authored command correction, timeout audit, unrestricted deconstruction marking, and map-ping cases;
- queue isolation, failure containment, and provider/RCON timeouts.

The 25 scenarios in `FULL_BOT_REQUIREMENTS.md` remain the initial end-to-end acceptance suite. Each implementation increment must map tests to stable requirement IDs.

## 12. Key decisions and deferred choices

Decisions fixed by this design:

- Python modular monolith, append-only UTF-8 text archive, small atomic flat-text state files, and rebuilt in-memory indexes; no first-release JSON or SQLite storage dependency.
- Groq provider initially, behind a replaceable gateway, with no automatic Ollama fallback.
- Deterministic-first routing and direct authoritative answers.
- Registered query plans plus permissive model-authored Lua/RCON with lightweight practical checks.
- A separate player-requested structured ghost-placement state machine.
- Ephemeral three-exchange per-player conversation memory.
- Application-owned rendering, preferences, welcomes, authority, and self-description.
- Model-owned language understanding, ambiguity resolution, comparison framing,
  tool/calculator/design planning, clarification wording, and answer synthesis;
  no local semantic regex catalog, fuzzy intent engine, or question-specific
  handler layer.

Choices intentionally deferred until implementation evidence is available:

- Archive maintenance tooling beyond retained 10 MB numbered segments.
- The initial breadth and pagination size of each read-only domain adapter.
- Which lightweight checks improve the selected model's observed Lua/RCON reliability without becoming a restrictive security framework.
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
