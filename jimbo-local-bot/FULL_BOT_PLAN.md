# Jimbo Full Bot Implementation Plan

Status: proposed serial implementation roadmap (2026-07-21)

## Objective

Build the first full release of Jimbo the Jr. Engineer as specified by
`FULL_BOT_REQUIREMENTS.md` and architected in `FULL_BOT_DESIGN.md`, without
turning the completed proof of concept into an open-ended patch series.

The full bot must preserve the proven public-chat loop while adding durable
event ingestion, deterministic authority and routing, broad bounded read-only
investigation, deterministic calculations, player preferences, automatic
welcomes, a canonical archive, and management-only ghost placement.

## Source-of-truth order

When documents differ, use this order:

1. `FULL_BOT_REQUIREMENTS.md` defines required product behavior and stable
   requirement IDs.
2. `FULL_BOT_DESIGN.md` defines the architecture and system boundaries.
3. This plan defines implementation sequence, step scope, and completion gates.
4. `FULL_BOT_FINDINGS.md` provides player-testing evidence and examples.
5. `POC_PLAN.md` records POC history and is not the full-bot architecture.

Implementation discoveries may refine the design and plan, but must not weaken
a normative requirement without an explicit product decision recorded in the
requirements document.

## Step convention

The implementation is divided into fourteen serial top-level steps. A request
such as `implement full bot step 3` means the entire matching section,
including its tests, documentation, and acceptance check.

Complete and verify each step before beginning the next unless the user
explicitly requests multiple steps together. A step may contain several
activities, but those activities are not independent project-level step
numbers. If a step uncovers a blocking architectural choice, record the choice
in `FULL_BOT_DESIGN.md` and this plan before proceeding.

Every completed step must:

- preserve existing POC behavior unless the step explicitly replaces it;
- add or update dependency-free automated tests where practical;
- avoid live Groq calls and live RCON in routine tests;
- use recorded fixtures or mocks for provider, log, and RCON behavior;
- update operator/user documentation for changed behavior;
- map new tests to the relevant stable requirement IDs;
- record material decisions and deferred work in this document;
- leave the working tree understandable and the bot recoverable.

Live validation is permitted only when a step explicitly calls for it. Live
RCON must use the repository's fixed wrapper and follow the incremental safety
rules in `AGENTS.md`.

## Step 1: Establish the full-bot application boundary

### Scope

Create the full-bot code structure and typed contracts without changing the
active POC listener or sending any live chat.

### Work

1. Choose and create a separate full-bot package/entry point within
   `jimbo-local-bot`; do not silently convert the POC entry point in place.
2. Define typed configuration for paths, provider/model, timeouts, chat budget,
   queue limits, public-reply state, welcome state, archive rotation, and
   management identity.
3. Define core contracts for normalized events, request plans, authority
   decisions, tool results, provenance, rendered messages, delivery results,
   and error categories.
4. Define interfaces for the event source, archive, state store, router, model
   gateway, calculator, read-only tools, placement service, renderer, and
   delivery transport.
5. Load secrets only from existing ignored runtime paths. Reject secrets in
   ordinary configuration serialization or diagnostic output. Reuse the
   existing `runtime/groq-api-key.txt` path without reading it during offline
   startup, replacing it, relocating it, printing it, or requiring the user to
   re-enter it.
6. Add a full-bot test entry point and fixture directories while retaining the
   existing POC test command.

### Tests

- Configuration defaults and overrides validate deterministically.
- Invalid limits, paths, provider settings, and management identities fail
  clearly.
- Contract serialization round-trips without losing provenance or status.
- Secret values cannot appear in configuration dumps or structured diagnostics.
- Offline startup and tests neither read nor validate the Groq key and make no
  request for a new or re-entered key.
- Importing and starting the full-bot shell performs no provider or RCON call.

### Acceptance check

The full-bot shell starts in disabled/offline mode, reports validated runtime
configuration with secrets redacted, and exits cleanly without reading live
chat, contacting Groq, or invoking RCON.

### Primary requirements

AUTH-001, AUTH-002, AUTH-004, OPS-001, OPS-003, QUAL-003, QUAL-004.

### Step 1 result (2026-07-21)

Status: complete; acceptance check passed.

- Added the separate `jimbo_full_bot` package and `python -m jimbo_full_bot
  --offline` entry point without modifying the POC listener entry point.
- Added validated, immutable configuration for provider/model, paths, timeouts,
  limits, feature switches, and the case-insensitive management identity.
- All live capabilities default to disabled. Feature dependencies prevent
  welcomes, public replies, or placement from being enabled without their
  required delivery/RCON capability.
- Added typed contracts for normalized events, routing, authority, provenance,
  tool results, rendering, delivery, statuses, and error categories, including
  plain-data round-trip validation for events and provenance-bearing results.
- Added dependency interfaces for event source, archive, state, routing,
  authority, model, calculator, read-only tools, placement, rendering, delivery,
  and secret reading. No concrete live dependency is wired in Step 1.
- The existing ignored `runtime/groq-api-key.txt` is referenced by path only.
  Offline construction, diagnostics, and tests do not read, validate, move,
  print, or replace it.
- Added 18 dependency-free Step 1 tests. The complete POC plus full-bot suite
  now has 62 passing tests and makes no live provider or RCON call.
- The actual offline entry point printed a redacted status with log watching,
  RCON, public replies, welcomes, and placement disabled, then exited cleanly.

Decision: retain the full bot as a separate package while the POC remains the
active listener. Do not add the full bot to background lifecycle controls until
a later step explicitly enables live operation.

## Step 2: Implement the flat-file event archive and state

### Scope

Create the durable append-only UTF-8 text event archive and only the small
atomic flat-text state files needed for restart safety before building
ingestion or replies. Do not add JSON storage or a database in this step.

### Work

1. Define a minimal versioned tagged-line archive format for source events,
   routing, tool use, model generation, rendering, delivery, greetings, errors,
   and placement. Keep each physical record on one UTF-8 line and define
   deterministic escaping for tabs, newlines, backslashes, and controls.
2. Implement immediate append-and-flush behavior and segment rotation without
   deleting old segments.
3. Define versioned line-oriented text formats for cursors, seen players,
   preferences, deliveries, runtime flags, placement runs, and placement
   batches.
4. Update mutable text state through write-to-temporary-file, flush, and atomic
   replace so interruption cannot leave a partially written state file.
5. Make archive records the reconstructable source of truth and rebuild any
   needed query indexes in memory.
6. Add startup integrity checks and archive-segment iteration.
7. Add secret/control-character rejection and privacy-safe serialization.
8. Choose and record initial archive rotation thresholds. Keep all public chat
   for the life of this single-server deployment.

### Tests

- Append, escaping/unescaping, flush, rotation, restart, and cross-segment
  iteration.
- Duplicate event IDs are rejected or treated idempotently.
- An intentionally discarded in-memory index can be rebuilt from the text log.
- Truncated final archive records are detected and handled without losing prior
  valid records.
- API keys, RCON credentials, environment dumps, and hidden prompts are never
  serialized.
- Schema migration preserves existing fixture data.

### Acceptance check

A fixture event lifecycle can be written, flushed, reopened, reconstructed
solely from the UTF-8 text log, and queried through a rebuilt in-memory index.
Mutable state survives restart through atomic flat-text files, with no JSON
storage, database, ambiguous record boundary, or secret leakage.

### Primary requirements

ARCH-001 through ARCH-007, QUAL-001, QUAL-004.

### Step 2 result (2026-07-21)

Status: complete; acceptance check passed.

- Added an append-only UTF-8 tagged-line archive with one physical line per
  record and deterministic escaping for tabs, newlines, returns, backslashes,
  and remaining control characters.
- Archive records carry version, UTC time, kind, event ID, correlation ID,
  actor, and readable payload. The format supports source events, routing,
  tools, model output, rendering, delivery, errors, greetings, and placement
  without JSON or a database.
- Every append is flushed and synchronized immediately. Duplicate non-empty
  event IDs are idempotent, including after restart.
- The active `events.log` rotates before exceeding 10 MB into monotonically
  numbered retained segments. Segment iteration preserves chronological order
  and never deletes historical public chat.
- Startup scans report malformed or truncated records while retaining valid
  records before and after a bad complete line. In-memory event indexes rebuild
  from the text archive alone.
- Added atomic versioned flat-text state files for cursors, seen players,
  preferences, deliveries, runtime flags, placement runs, and placement
  batches. Updates use temporary-file write, flush, synchronization, and atomic
  replace.
- Added startup state integrity checks and a backed-up migration from the
  earlier simple `key=value` fixture format.
- Secret-shaped API-key, authorization, RCON-password, and hidden-prompt fields
  are rejected before archive serialization. The implementation does not read
  the real Groq key or RCON password.
- Added 17 dependency-free Step 2 tests. The complete suite now has 79 passing
  tests and makes no live provider, RCON, or server-log call.

Decision: keep the first release on the simple text archive and text state
files. Use 10 MB retained archive segments and add structured storage only if
later operational evidence demonstrates a concrete need.

## Step 3: Implement durable log ingestion and event normalization

### Scope

Ingest all new complete public chat and join/leave records, including records
written while the full bot is stopped, without producing replies yet.

### Work

1. Reuse proven binary tailing behavior where appropriate, but write normalized
   events through the new archive/state contracts.
2. Track source identity, byte boundaries, durable byte position, and
   content-derived event identity.
3. Detect ordinary append, partial lines, restart, truncation, replacement, and
   rotation.
4. Parse public chat, player join, and player leave records into typed events.
5. Archive every complete supported public event before advancing the durable
   cursor.
6. Record malformed and unsupported records as bounded diagnostics without
   routing them as requests.
7. Expose ingestion lag and last-event status without enabling any response.

### Tests

- Start, stop, append while stopped, and resume from the durable cursor.
- Partial UTF-8 and partial-line boundaries across polling cycles.
- Truncation/rotation creates a new source identity without replaying old
  events or skipping new ones.
- Malformed, diagnostic, join, leave, chat, and bot-authored fixtures classify
  correctly.
- A crash between archive append and cursor update reprocesses idempotently.

### Acceptance check

An offline fixture simulates stop/restart, appended records, a partial line,
and log rotation. Every complete public chat/join/leave event appears exactly
once in the canonical archive and no reply is attempted.

### Primary requirements

EVT-001, EVT-002, EVT-006, ARCH-002, ARCH-004, QUAL-001.

### Step 3 first-pass result (2026-07-21)

Status: first pass complete; sufficient for Steps 4-7 and the offline
acceptance check.

- Added a separate full-bot durable reader that starts at the current log end
  on first launch, resumes from the atomic flat-text cursor after restart, and
  reads only complete appended byte lines.
- Cursor state includes resolved path, stable source identity, committed byte
  offset, a 128-byte checkpoint, and last event ID. Replacement, truncation,
  and checkpoint mismatch restart at the beginning of the new contents.
- Added normalization for the live server's verified `[CHAT]`, `[JOIN] <player>
  joined the game`, and `[LEAVE] <player> left the game` formats.
- Normalized events carry deterministic SHA-256 identity, source identity,
  exact byte start/end, timezone-aware source time, actor, raw line, and chat
  message where applicable.
- The ingestion service appends and synchronizes the archive record before
  advancing the cursor. A crash replay is idempotent through the Step 2 event
  ID index.
- Unsupported or malformed complete lines become bounded diagnostics and do
  not stop later records. Partial lines are neither archived nor committed.
- Normalized public events can be reconstructed from the text archive without
  JSON. Secret-shaped chat is redacted in the archive without blocking cursor
  progress.
- Added 11 dependency-free Step 3 tests covering first start, stopped-period
  records, partial lines, archive failure/retry, crash replay, truncation,
  replacement, diagnostics, normalization, reconstruction, and redaction. The
  complete suite now has 90 passing tests.
- Read-only inspection confirmed that current live server join/leave lines
  match the implemented formats. The full-bot reader was not started against
  the live log and no production cursor was created.

Deferred for a later hardening pass: a continuously polling full-bot runtime,
missing-file/backoff handling, race hardening for replacement during a read,
DST-aware historical source-time configuration, and large-log chunking. These
are not required by Steps 4-7, which consume the normalized event interface.

## Step 4: Implement invocation, self-loop prevention, and welcomes

### Scope

Decide which normalized events become requests or greetings, still without a
model call or general conversational reply.

### Work

1. Implement deterministic leading `jimbo` and `hey jimbo` invocation parsing,
   case-insensitively with ordinary punctuation.
2. Add narrowly defined and tested minor-variant tolerance without triggering
   on `jimbob`, quotations, third-person discussion, or unrelated text.
3. Identify and suppress Jimbo's own delivered public records.
4. Implement case-insensitive seen-player state with latest display spelling.
5. Generate deterministic first-seen and returning-player greetings.
6. Every welcome and welcome-back message must instruct players to begin their
   queries with `Jimbo`; the template must remain short and compatible with
   `Hey Jimbo`.
7. Add welcome enable/disable and temporary suppression flags.
8. Prevent greetings for replayed historical joins and bot startup while
   players remain online.

### Tests

- Invocation punctuation, casing, accepted variants, empty request, `jimbob`,
  quotations, third-person mentions, and self-authored chat.
- First join, returning join, case-changed name, reconnect churn, restart,
  historical replay, disable, and temporary suppression.
- Every delivered greeting fixture contains the explicit `Jimbo` invocation
  instruction and contains no prior activity detail.
- No greeting path calls the model.

### Acceptance check

Recorded join and chat fixtures produce exactly the expected accepted requests
and welcome/welcome-back intents, with no duplicates or model calls. Every
greeting tells the player to begin queries with `Jimbo`.

### Primary requirements

EVT-003 through EVT-005, WELCOME-001 through WELCOME-009.

### Step 4 first-pass result (2026-07-21)

Status: first pass complete; sufficient for Steps 5-7.

- Added deterministic, case-insensitive parsing for required leading `Jimbo`
  and `Hey Jimbo` forms with ordinary whitespace and punctuation cleanup.
- Longer words such as `jimbob`, later/third-person mentions, quoted
  invocations, unrelated chat, and non-chat events are not accepted.
- Chat attributed to `<server>`, `server`, or `Jimbo` is explicitly classified
  as self-authored and cannot create a response loop.
- Accepted decisions contain the original event/actor and normalized request
  text. Empty but explicit invocations remain accepted for later friendly
  handling.
- Added durable case-insensitive seen-player classification with latest display
  spelling, pending/delivered join-event state, disabled/suppressed state, and
  restart replay behavior in the Step 2 flat-text store.
- First joins produce `Welcome, <name>! Begin queries with Jimbo.` and later
  distinct joins produce `Welcome back, <name>! Begin queries with Jimbo.` No
  welcome path has a model dependency.
- A pending welcome intent survives restart for Step 5 delivery; a delivered,
  disabled, or suppressed join event produces no duplicate intent.
- Added 13 dependency-free Step 4 tests. The complete suite now has 103 passing
  tests and makes no live provider, RCON, or full-bot log call.

Deferred for a later hardening pass: carefully scoped fuzzy invocation
variants, invocation/welcome decision records in the canonical archive,
runtime operator-flag wiring, concurrent state-update locking, and reconciliation
of the narrow crash gap between an external successful greeting send and its
local delivered-state commit. These do not block Steps 5-7.

## Step 5: Stub the minimal safe renderer and delivery path

### Scope

Create the smallest safe path that can turn one plain-text application reply
into one public Factorio chat line through the proven fixed RCON credential
flow. This is a prototype-enabling stub, not completion of the full renderer
requirements.

### Work

1. Reuse the proven POC public-reply format and fixed RCON wrapper path.
2. Collapse line breaks and repeated whitespace, remove control characters, and
   produce exactly one plain-text chat line.
3. Apply a deliberately conservative character limit. Reject overlong output
   with a short safe fallback instead of paginating or truncating it.
4. Treat the rendered content only as inert `game.print` text and prevent it
   from escaping the local Lua long string. Do not add broad command/artifact
   content filtering, trusted rich text, or GPS links yet.
5. Implement one serial delivery worker with a timeout, no automatic retry, an
   exact sent-text archive record, and a delivery outcome.
6. Keep public delivery disabled by default and provide a fake transport for
   tests.
7. Record full rendering, precise byte budgeting, pagination, Unicode edge-case
   hardening, and rich-text support as a required Step 5 follow-up pass.

### Tests

- Plain ASCII and ordinary valid Unicode survive single-line normalization.
- Line breaks, repeated whitespace, and control characters are removed.
- Conservative limit, over-limit fallback, and Lua long-string containment.
- Queue ordering, timeout, permanent failure, and duplicate delivery
  suppression.
- Exact rendered and sent strings appear in the archive.

### Acceptance check

The minimal renderer passes its bounded plain-text safety fixtures, then a
staged harmless message traverses the fixed RCON wrapper and appears exactly
once in Factorio. Public conversational replies remain disabled. Completion of
this step does not claim full ART or RENDER requirement coverage.

### Primary requirements

RENDER-001 through RENDER-003 and OPS-004. ART content classification and the
remaining RENDER coverage remain owned by a later Step 5 follow-up pass;
model/player text is printed inertly and never interpreted as an executable
command.

### Step 5 first-pass result (2026-07-21)

Status: minimal delivery bridge complete; sufficient for Steps 6-7.

- Added a plain-text renderer for normal replies and Step 4 welcome intents.
  It preserves ordinary Unicode, collapses whitespace/control characters,
  removes brackets to disable Factorio rich text and contain Lua long strings,
  and produces exactly one chat line.
- Replies use `Jimbo to <player>: <text>` and welcomes use `Jimbo: <welcome>`.
  An overlong reply is replaced with one complete short fallback rather than
  truncated into misleading output.
- Command-shaped player/model text is permitted for this trusted-player
  prototype but remains inert inside one locally constructed `game.print` long
  string. It is never interpreted as Lua, RCON, shell, or a slash command.
- Added the fixed-wrapper transport with a 15-second default timeout, one
  attempt, confirmation-marker requirement, and exact restoration of
  `tools/rcon-command.txt` after success or failure.
- Added a locked serial delivery worker. Public delivery defaults disabled;
  enabled delivery archives the rendered text and result, records confirmed
  correlation IDs for duplicate suppression, and performs no automatic retry.
- Confirmed welcome delivery marks the Step 4 pending intent delivered only
  after the transport returns success.
- Added 10 dependency-free Step 5 tests. The complete suite now has 113 passing
  tests, including containment, fixed-wrapper restoration, confirmation,
  single-attempt failure, serialization, exact archive text, deduplication, and
  welcome completion.
- A direct fixed-wrapper staged smoke message returned
  `JIMBO_FULL_REPLY_SENT`. The command file was restored to `/players`; the POC
  listener remained running, and no full-bot listener was started.

Deferred to a later Step 5 follow-up pass: broad command/artifact content
classification, precise encoded byte budgets, pagination, trusted rich text/GPS
construction, full Unicode edge-case hardening, bounded retry policy, and
reconciliation of the external-send/local-commit crash gap.

## Step 6: Stub the conversation handoff router

### Scope

Add only the thin authority-aware handoff needed to feed accepted Step 4
requests into the real model integration in Step 7. This stub does not perform
live RCON queries or complete any authoritative direct-answer requirements.

### Work

1. Convert each accepted Step 4 invocation into a typed conversation plan.
2. Attach an application-owned authority decision recognizing only
   case-insensitive `dlbattle` as management; expose no action tools in this
   stub, even for management.
3. Attach the small static server blurb already proven by the POC: Factorio
   2.1.12 with Space Age, Elevated Rails, and Quality.
4. State in that context that no fresh live snapshot was collected so the model
   should not claim current players, research, map, inventories, or other live
   facts.
5. Pass all accepted questions, including online/research questions, to Step 7
   conversation for now.
6. Leave deterministic online/research answers, action-request classification,
   historical presence, joins/leaves, health/configuration, deployed-version
   answers, privacy-scoped archive queries, stale/partial status policy, and the
   complete route catalog for a later Step 6 follow-up pass.

### Tests

- Accepted invocations become conversation plans with no allowed tool family.
- Rejected/ignored Step 4 decisions do not become plans.
- Only case-insensitive `dlbattle` receives the management identity flag.
- The static context contains the configured game blurb and explicitly says no
  fresh live observation was collected.
- Questions about players/research remain conversation routes; no RCON runs.

### Acceptance check

Offline fixtures show that accepted invocations become authority-aware
conversation plans with the small static game blurb and no tools or live query.
Completion does not claim authoritative ROUTE, STATE, or SELF coverage.

### Primary requirements

AUTH-001, AUTH-002, and the typed handoff needed by Step 7. Direct-answer ROUTE,
STATE, SELF, and remaining AUTH coverage remain owned by a later Step 6
follow-up pass.

### Step 6 stub result (2026-07-21)

Status: conversation handoff stub complete; sufficient for Step 7.

- Added a thin router that converts accepted Step 4 invocation decisions into
  typed `conversation` plans and ignores rejected decisions.
- Authority tagging remains application-owned: only case-insensitive
  `dlbattle` receives the management flag. Conversation is allowed for all
  players, but the stub exposes no tool family or action capability to anyone.
- Every handoff includes the small POC-proven static blurb identifying Factorio
  2.1.12, Space Age, Elevated Rails, and Quality.
- The context explicitly states that no fresh live snapshot was collected and
  instructs the model not to claim current players, research, map, inventory,
  production, or other current-save facts.
- Online, research, and action-shaped questions remain ordinary tool-free
  conversation for the prototype. This step performs no RCON query and provides
  no deterministic direct response.
- Added 6 dependency-free Step 6 tests. The complete suite now has 119 passing
  tests.

Deferred to a later Step 6 follow-up pass: all authoritative direct routes,
current players/research, action classification and useful authority declines,
archive/history queries, runtime self-description, stale/partial status
handling, and the complete routing catalog.

### Step 6 basic live-state follow-up result (2026-07-21)

- Added deterministic phrase routing for connected players, current research
  and progress, game time, and available surfaces.
- Recognized requests select one locally authored fixed read-only RCON snapshot.
  The model cannot select, write, or modify the command. Answers are formatted
  directly from parsed trusted values.
- Unrecognized requests continue through ordinary Step 7 conversation without
  RCON. A future Step 6 pass may add a bounded intelligent state-needs
  classifier, but it must still select only locally approved operations.
- Added three tests, bringing the complete suite to 131 passing tests. A live
  read-only smoke confirmed the expected output shape.
- Restarted the active prototype with this capability, verified PID 9056, and
  announced the revision and its limitations in public chat.
- Live testing exposed Windows/RCON replacement glyphs for model-produced
  typographic Unicode. The Step 5 renderer now transliterates punctuation and
  accented text to readable ASCII before delivery. A regression test brings
  the complete suite to 132 passing tests; the listener was restarted with the
  fix and verified running as PID 22476.

### Step 6 target follow-up: model-directed state-needs planning

Replace phrase matching as the primary state-needs decision mechanism with one
bounded model planning pass while preserving local ownership of every executable
operation.

#### Work

1. Define a strict provider-neutral `StateNeedsPlan` containing zero or more
   allowlisted tool names and no free-form code. Begin with
   `get_connected_players`, `get_current_research`, `get_game_time`, and
   `get_available_surfaces`.
2. Give the planner the current player request, relevant per-player history,
   tool descriptions, and runtime policy, but no RCON credentials, command
   templates, hidden filesystem data, or authority to expand the allowlist.
3. Perform at most one planning call. Reject unknown tools, extra fields,
   arguments where none are allowed, excessive tool count, malformed output,
   mutation requests, Lua, and RCON text before execution.
4. Map every accepted tool name to locally authored fixed read-only RCON code.
   The model may select an operation but can never author or modify its command.
5. Execute accepted operations through the serial read-only RCON boundary and
   return trusted values with source, collection time, completeness, status,
   scope, and warnings.
6. Make at most one answer-generation call after planning. Separate tool
   results from untrusted player text and require the answer to preserve result
   provenance and unknown/stale/partial qualifiers.
7. When the plan requests no state, continue ordinary conversation without
   RCON. When planning or RCON fails, provide a transparent bounded fallback
   and do not invent live facts.
8. Archive the planning decision, validation outcome, selected operations,
   query timing/status, safe result summary, synthesis outcome, and delivery.
9. Keep the existing deterministic phrase matcher temporarily as a rollout
   fallback and comparison path. Remove or narrow it only after staged tests
   show the planner reliably requests state without excessive RCON use.

#### Tests

- Natural and indirect questions select the necessary approved tools, while
  general knowledge and casual conversation select none.
- Follow-ups such as `how do you know that?` receive the prior observation's
  provenance rather than contradicting it or unnecessarily repeating RCON.
- Prompt injection, arbitrary tool names, Lua/RCON text, extra fields, and
  mutation requests execute nothing.
- Tool selection cannot exceed the configured count or recurse into additional
  planning passes.
- Trusted fresh/partial/unavailable results remain correctly qualified in the
  synthesized answer despite contradictory player text or model output.
- Routine tests mock both model calls and RCON and consume no hosted quota.

#### Acceptance check

Staged conversations demonstrate that the model requests approved live state
when needed, skips RCON when it is not needed, explains how fresh observations
were obtained, and cannot cause any operation outside the local read-only
allowlist. A bounded hosted smoke and harmless live RCON smoke pass before the
planner becomes the primary live path.

#### Implementation progress (2026-07-21)

- Added a provider-neutral `StateNeedsPlan` with exactly four initial operations:
  connected players, current research, game time, and available surfaces.
- The model owns natural-language state-needs selection through one strict
  planning call. Local code performs schema and allowlist validation only; it
  does not add another intent classifier or expand the phrase catalog.
- Approved selections project one locally authored fixed read-only RCON snapshot
  into provenance-bearing tool results. One answer pass receives those results
  separately from player text and conversation history.
- The latest successfully delivered observation is retained per player for
  model-handled provenance follow-ups. The phrase matcher is consulted only if
  planning fails during rollout.
- Planning, validation, selected tools, safe query timing/status, synthesis, and
  delivery lifecycle events are archived. Routine tests mock provider and RCON.
- The complete dependency-free suite passes 137 tests. A bounded hosted/live
  smoke selected connected players plus surfaces for an indirect compound live
  question, executed one harmless fixed snapshot, and synthesized the observed
  values. A second hosted smoke selected no tools for a generic splitter
  question. Neither smoke delivered public chat. The managed listener was
  restarted onto this revision as PID 17992, verified running, and the change
  was announced publicly under OPS-006.

## Step 7: Integrate the model and bounded per-player conversation

### Scope

Add provider-backed generic conversation and follow-ups while preserving all
deterministic boundaries.

### Work

1. Implement the replaceable model gateway with Groq
   `openai/gpt-oss-120b` as the initial deployment and no automatic Ollama
   fallback.
   This implementation pass must include the real hosted call path; a stub-only
   gateway is insufficient.
2. Separate trusted facts, tool provenance, untrusted player text, recent
   conversation, and policy instructions in requests.
3. Add the last three completed exchanges separately per player in memory.
4. Commit history only after a player-visible reply is successfully delivered.
5. Resolve short follow-ups against recent subject matter and ask concise
   clarifications for material ambiguity.
6. Support harmless non-Factorio conversation and PG-13 personality while
   preserving runtime-owned capability statements.
7. Prevent disclosure of raw prompts, hidden context, credentials, reasoning,
   or another player's conversation.

### Tests

- Provider payload, timeout, malformed response, missing content, and replaceable
  provider contract.
- Three-exchange limit, player isolation, restart loss, and successful-delivery
  commit.
- Provider error, renderer rejection, and delivery failure do not enter memory.
- `EM` and similar follow-ups resolve from relevant subject matter or clarify.
- One player's Swedish instruction cannot affect another player.
- Runtime facts survive contradictory model output.

### Acceptance check

Two-player mocked conversations demonstrate isolated three-exchange memory,
correct follow-ups, and failure exclusions. A staged hosted smoke test produces
one relevant bounded reply through the real Groq API and existing key file
without weakening direct-answer authority. Do not request or replace the key.

### Primary requirements

ROUTE-004 through ROUTE-006, KNOW-001, KNOW-002, CONV-001 through CONV-005,
SOC-001 through SOC-005, PREF-005, PREF-006, OPS-005.

### Step 7 implementation result (2026-07-21)

Status: complete; the playable full-bot prototype is active.

- Added a replaceable standard-library Groq gateway using
  `openai/gpt-oss-120b`, the existing ignored key file, a bounded timeout, and
  no automatic Ollama fallback.
- Provider messages keep runtime policy, trusted static context, bounded
  per-player history, and untrusted current player text in distinct messages.
- Added case-insensitive per-player memory containing at most the last three
  exchanges. Memory is committed only after confirmed public delivery and is
  deliberately lost on restart.
- Added the live orchestration path connecting durable ingestion, deterministic
  invocation, Step 6 routing, Groq, minimal rendering, and fixed-wrapper RCON
  delivery. Welcome delivery is active through the same runtime.
- Added nine quota-free Step 7 tests. The complete POC/full-bot suite has 128
  passing tests.
- One local-only hosted smoke used the existing key and returned a relevant,
  bounded splitter answer. It did not send a message to Factorio.
- Replaced the managed POC listener with the full-bot prototype listener. It
  started cleanly and was verified running as PID 23780; always use the managed
  status action rather than relying on this recorded PID.
- Announced the new prototype revision publicly with a short summary of its
  invocation, conversation, follow-up-memory, and welcome capabilities plus its
  current live-fact/action limitation. Future replacements must do the same
  under OPS-006.

## Step 8: Implement durable player preferences and presentation safety

### Scope

Add the small approved preference allowlist independently from conversation
memory.

### Work

1. Let the model interpret inspect, set, edit, and reset requests and propose a
   strict typed preference operation for the authenticated player.
2. Start with `facts_only` versus `facts_and_advice` and only explicitly
   approved presentation transformations.
3. Validate ownership and the small value allowlist locally, then store
   preferences durably with schema version and timestamps.
4. Give response preferences to the model. For `facts_only`, require structured
   facts, assumptions, warnings, and advice sections; local code may omit the
   explicitly tagged advice section but must not classify arbitrary prose.
5. Limit local presentation transformations to mechanical operations that do
   not require recognizing factual spans or understanding meaning.
6. Preserve commands, coordinates, names, recipes, quantities, and units by
   construction in structured fields or leave the response untransformed.
7. Supply a readable untransformed fallback when a transformation is unsafe or
   unsupported.

### Tests

- Ownership, case-insensitive identity, inspect, edit, reset, and restart.
- One player cannot set another player's or global preferences by assertion.
- Model-produced structured facts-only output omits only the tagged advice
  section without removing material assumptions or warnings.
- Local code does not infer facts versus advice from arbitrary prose.
- Mechanical transformations cannot corrupt structured factual values or create
  executable-looking output.
- Unsupported transformations use the readable fallback.

### Acceptance check

Two-player restart fixtures show durable isolated preferences, successful
inspection/reset, and unchanged factual protected spans.

### Primary requirements

PREF-001 through PREF-004, ARCH-007.

## Step 9: Implement the deterministic Factorio calculator

### Scope

Provide reproducible ratio, throughput, crafting, module, power, and furnace
calculations with explicit assumptions.

### Work

1. Define versioned data inputs and schemas for recipes, items, qualities,
   machines, crafting speeds, modules/beacons, belt throughput, and relevant
   modifiers.
2. Implement calculation primitives with units and defined rounding.
3. Let the model recognize calculation intent and propose typed calculator
   inputs; do not add local natural-language routing or parsing rules.
4. Return missing fields, invalid prototypes, units, versions, and authoritative
   candidate matches as structured validation results. The model asks focused
   clarification questions.
5. Let the model interpret `best` and propose comparison dimensions such as
   throughput, efficiency, power, pollution, space, and cost; local code
   computes only the requested validated dimensions.
6. Include assumptions, game-data version, and recomputable inputs in results.

### Tests

- Known furnace, belt, production-time, crafting, module, power, and quality
  fixtures.
- Unit consistency, rounding edges, invalid prototypes, and unsupported game
  versions.
- Changing any input recomputes the complete result.
- The model clarifies ambiguous `best` and materially incomplete inputs from
  structured validator feedback instead of local semantic heuristics.
- Model text cannot change deterministic numeric output.

### Acceptance check

The furnace-count and production-time acceptance scenarios reproduce expected
results from explicit inputs and assumptions, including corrected-input
recalculation.

### Primary requirements

KNOW-003 through KNOW-005, ROUTE-002, ROUTE-003.

## Step 10: Implement the bounded read-only query engine

Status: minimal core implemented and deployed. The model can propose up to six
strictly validated investigation steps from an application-owned catalog. The
first platform operations are registered and execute through one fixed,
read-only snapshot with local row/result bounds and provenance. Generic
filtering, grouping, aggregation, pagination, relationship traversal, queueing,
cancellation, and full status/timeout semantics remain pending.

### Scope

Build the safe structured discovery/filter/projection/aggregation engine before
adding broad domain coverage.

### Work

1. Define the versioned JSON investigation-plan schema and registered operation
   allowlist.
2. Implement validation for types, fields, scopes, limits, references, maximum
   steps, result bytes, and execution time.
3. Compile accepted operations into trusted read-only Lua/RCON templates; never
   execute model-authored code.
4. Implement discovery, filtering, projection, counting, grouping,
   aggregation, pagination, and relationship traversal primitives.
5. Add a serial bounded RCON investigation queue and cancellation/timeouts.
6. Return provenance and `complete`, `partial`, `timeout`, `unavailable`, or
   `stale` status for every result.
7. Reject mutation-shaped APIs and validate non-mutation independently of the
   planner.
8. Choose and record initial step, object, byte, page, and time bounds.
9. Publish an application-owned capability catalog of registered domains,
   operations, typed arguments, output fields, relationships, and limitations
   for the planner and runtime-owned capability answers.
10. Keep language understanding in the model. Do not add a local query-intent
    taxonomy, semantic regex catalog, or one hard-coded handler per question.
11. Replace catalog growth as the primary model interface with a compact,
    familiar read-only Lua-shaped query syntax. Parse it into a restricted AST,
    validate only allowlisted Factorio reads and bounded control flow, and
    compile it to trusted local templates; never execute the model text.
12. Reject assignments, mutation-capable methods, dynamic evaluation,
    metaprogramming, recursion, unrestricted globals, command registration, and
    unbounded iteration structurally. Do not rely on a textual denylist.
13. Retain the current registered operations as a tested fallback while the
    compiled interface is developed and compared for prompt size and accuracy.

### Tests

- Valid plan parsing/compilation and invalid operation/field/type rejection.
- Mutation attempts, arbitrary Lua/RCON, unbounded iteration, excessive joins,
  and oversized projections fail before RCON.
- Pagination, aggregation, timeout, partial results, and provenance propagation.
- Fuzzed plan input cannot escape the registered operation set.
- Static and staged checks confirm templates perform no mutation.
- Capability/schema questions use the registered catalog and cannot cause the
  model to invent fields or trigger arbitrary API reflection.
- Natural paraphrases produce model-authored structured plans without adding
  local phrase rules; unrelated conversation performs no RCON.
- Restricted Lua-shaped plans compile to the same bounded read-only executor;
  equivalent mutation, escape, reflection, and resource-exhaustion attempts are
  rejected before RCON.
- Prompt fixtures demonstrate that the fixed syntax contract is compact and
  does not require restating a growing operation catalog on every request.

### Acceptance check

A mocked multi-step plan filters and aggregates a bounded dataset with complete
provenance, while mutation and arbitrary-code adversarial plans are rejected.
A harmless staged query confirms the compiler/executor contract.

### Next Step 10 increment

Design and prototype the parser/compiler boundary before adding more canned
domain queries. Start with logistics and platform reads already covered by the
trusted adapters, so compiled queries can be compared directly against known
answers and load behavior. Measure prompt characters/tokens, plan validity,
RCON command/result size, execution time, and correction frequency. Do not
remove the existing operations or activate compiled model queries publicly until
offline adversarial tests and harmless no-public live comparisons pass.

### Primary requirements

STATE-006, STATE-007, STATE-009 through STATE-012, QUAL-003, QUAL-006.

## Step 11: Add broad live-state domain adapters and investigations

Status: platform and initial logistics/storage vertical slices implemented;
broad domain coverage remains pending. Platform coverage distinguishes display
name, platform surface, stopped orbital location, and transit connection.
Logistics coverage exposes bounded network identity/location, robot availability,
member counts, stored item totals, and sampled logistic-container inventories
and requests.

### Scope

Expand the query engine across the required observable Factorio domains and
support coherent multi-step answers.

### Work

1. Implement adapters, where Factorio exposes reliable data, for surfaces and
   planets; forces/progression; players; entities/ghosts; inventories, recipes,
   filters, requests, and controls; logistics; trains; space platforms;
   electric networks; statistics; pollution; resources; research; and map
   positions.
2. Add exact authoritative name/prototype/surface lookup that returns zero, one,
   or multiple candidates. The model resolves candidates from context or asks a
   clarification; local code never silently chooses a fuzzy semantic match.
3. Support bounded cross-domain relationships and joins.
4. Let the model propose only structured plans and validated arguments.
5. Have the model synthesize public answers from provenance-bearing results
   without dumping raw records or hiding incompleteness; adapters return facts
   and relationships, not locally inferred conclusions.
6. Produce coordinates only from observed validated positions and render GPS
   links through trusted local code.
7. Record the first-release coverage and any Factorio API limitations per
   domain.

### First vertical slice: space platforms

Implement this slice before the other Step 11 domains because post-Step-6 live
testing immediately exercised it and exposed the limitations of treating a
platform surface as a platform record.

1. Inspect and record the Factorio 2.1.12 API representation for platform stable
   identity, displayed name, internal surface identity, current location/status,
   schedule, hub inventory, logistic requests, and cargo relationships.
2. Add registered platform discovery and inventory operations using the Step 10
   schema. Keep display name and internal surface identifier distinct.
3. Support bounded selection, projection, item filtering, counting, and the
   relationship from a platform to its hub inventory, requests, and schedule.
4. Preserve object identities and the latest structured result per player so
   the model can resolve `that platform`, `which one`, and provenance follow-ups.
5. Answer platform capability/field questions from the registered capability
   catalog. Unsupported fields must be explicit rather than model-invented.
6. Stage these live questions without public delivery before activation:
   `What platforms exist?`, `What is that platform's displayed name?`,
   `Does any platform contain space science?`, `How much does each contain?`,
   `What is each requesting?`, and `Where is each going?`.

Implemented evidence (2026-07-21): schema/adversarial fixtures and hosted
planner/synthesis smokes passed; harmless live identity+cargo and
requests+schedule smokes passed; the complete suite reached 143 tests including
the post-deployment literal-bracket regression. The managed listener
was activated as PID 24400 and the iteration was announced publicly. Initial
player testing then exposed a renderer ambiguity for rich-text platform names;
the renderer now spells unsafe brackets as `left-bracket` and `right-bracket`
instead of silently deleting them.

After the platform slice, expand in evidence-driven order: logistic networks and
storage; production/consumption statistics; electric power and pollution;
trains/stations/schedules/cargo; bounded entity/inventory inspection; then
resources and observed map positions. Surfaces/planets, forces/progression, and
players are expanded as required by those relationships. Every domain remains
pending until its adapter contract, bounds, fixtures, and harmless live smoke
are recorded.

### Second vertical slice: logistics and storage

Implemented 2026-07-21 with four model-selectable operations:
`list_networks`, `count_items`, `inspect_contents`, and `inspect_containers`.
Exact network IDs
or custom names and exact surface/item/container prototypes are locally
validated. `count_items` uses Factorio's authoritative logistic-network count
for one exact item and distinguishes all members, providers (bot-available
supply), and storage. Exact-item container inspection applies surface,
prototype, numeric-network, and item scope before its bound and returns at most
128 relevant containers. Broader fixed templates return at most 32 networks,
128 item rows per network, 64 unscoped containers, and 32 inventory/request rows per container;
limit hits are marked partial and synthesis must not claim exhaustive coverage.
Templates were split at application-owned boundaries after live RCON exposed
the command-length ceiling. Hosted/live no-public smokes correctly reported
Nauvis steel and construction-robot availability and inspected a requester
chest in network 2. Platform location semantics were corrected at the same time:
`stopped_at_location` means stopped in orbit at the named space location, while
the `surface` field is only the platform's internal map surface.

Player feedback also replaced spelled-out trusted platform tags with a narrow
trusted-token renderer: exact live names such as `[item=space-science-pack]`
may render as Factorio icons, while arbitrary model-authored rich text remains
disabled.

The quota-safe breadth follow-up permits six steps, gives the planner one
schema-correction retry, mechanically compacts prior observations to 8,000
characters, and limits model-visible tool context to 16,000 characters. The
separate 200 KB result ceiling remains an RCON transport guard, not permission
to send that entire payload to the model. Provider token usage and safe
remaining-quota headers are archived when Groq supplies them. Hosted/live
no-public smokes reported 504 provider-available steel plates in Nauvis network
2 and 101 steel plates physically present in its requester chests. The full
dependency-free suite now passes 149 tests.

### Tests

- Adapter contract fixtures for every supported domain.
- Ambiguous names, missing surfaces, invalid prototypes, partial pages, stale
  snapshots, and unsupported fields.
- Aquilo logistic-chest/quantum-processor investigation.
- Space-platform resource origin/destination/cargo/request investigation.
- Platform display identity is not inferred from its internal surface name.
- Platform item-filter questions inspect authoritative hub cargo and distinguish
  empty, unavailable, partial, and unsupported results.
- Resource/map recommendations never invent patches or coordinates.
- Broad surface queries remain bounded and honest about partial coverage.

### Acceptance check

Recorded and staged fixtures pass the required Aquilo chest and space-platform
investigations with collection time, scope, object identities, and explicit
limitations. At least one harmless query per supported live adapter passes its
staged validation path.

### Primary requirements

STATE-005 through STATE-012, ROUTE-003 through ROUTE-005, QUAL-006.

## Step 12: Implement offline ghost-design validation and planning

### Scope

Build and test the complete structured placement contract without mutating the
live world.

### Work

1. Let the model interpret the requested layout and propose or revise a typed
   design; local code does not invent, optimize, or semantically improve it.
2. Define the versioned `GhostDesign` schema for Factorio version, surface,
   anchor, prototypes, exact centers, directions, qualities, recipes, filters,
   priorities, control behavior, wires, and module requests.
3. Implement blueprint decode, compact JSON validation, and encode/decode
   round-trip checks.
4. Reject duplicate centers, unknown/unsupported prototypes, invalid settings,
   invalid coordinates, incompatible versions, direct construction, tiles,
   destruction, deconstruction, inventory/player/research/force mutation, and
   unbounded operations.
5. Return precise structured validation errors to the model for explanation or
   a revised design; validators do not choose design alternatives.
6. Convert validated designs into deterministic representative-test,
   preflight, bounded-batch, audit, and scoped-cleanup plans.
7. Require a distinctive exact marker and explicit surface/anchor.
8. Keep raw model-authored Lua/RCON disabled. Any future proposal to enable it
   requires a separate recorded design decision and must reduce to the same
   structured allowlist.
9. Create immutable design hashes and full placement audit records.

### Tests

- Valid entity design and blueprint round trip.
- Factorio version, quality, direction, entity-center, footprint, recipe,
  filter, priority, wire, and module preservation.
- Duplicate, collision-shaped, unsupported, mutation-shaped, and unbounded
  designs fail validation.
- Batch plans are small, deterministic, and reproduce expected positions.
- Cleanup plans include only original expected positions and matching
  prototypes.
- Local code either validates the proposed layout or returns structured errors;
  it does not generate or optimize layouts on the model's behalf.

### Acceptance check

A representative multi-prototype design round-trips through the structured
format and produces deterministic marker, preflight, small-batch, audit, and
cleanup plans without executing RCON.

### Primary requirements

AUTH-006, ART-002, GHOST-001 through GHOST-004, GHOST-007 through GHOST-010.

## Step 13: Implement management-only live ghost placement

### Scope

Connect the validated placement plans to the dedicated live RCON pipeline with
authority checks, incremental execution, audit, and safe recovery.

### Work

1. Implement the placement state machine:
   `DISCUSS -> DRAFT -> VALIDATED -> MARKER_TEST ->
   AWAIT_LOCATION_CONFIRMATION -> PREFLIGHT -> BATCH_PLACE -> AUDIT ->
   COMPLETE`, with `ABORTED` transitions.
2. Recheck case-insensitive `dlbattle` authority at every state-changing
   transition and before every live batch.
3. Establish and report a distinctive exact marker GPS coordinate.
4. Validate and place one representative ghost of every prototype, audit it,
   and require location confirmation before material placement.
5. Scan the complete footprint for rails, entities, tiles, water, and
   collisions; call `surface.can_place_entity` for every planned entity and
   abort the main placement if any required position fails.
6. Place small bounded batches and audit every batch. Stop on explicit measured
   conditions: timeout, missing confirmation, configured response-time or queue
   threshold, audit mismatch, or operator abort. Audit before any retry; do not
   add a heuristic that the server merely `seems unhealthy`.
7. Verify exact prototypes, center positions, directions, qualities, recipes,
   filters/priorities, control behavior, wires, and module requests.
8. Implement separately authorized scoped cleanup/replacement using the
   original design positions and matching prototypes only.
9. Archive requester, authority decision, design hash, anchor, validation,
   commands, RCON results, batches, audits, failures, and final state.
10. Provide operator abort and an exclusive mutation lease. There is no general
    Lua/RCON executor.

### Tests

- Ordinary player, Factorio admin, spoofed identity, casing, and prompt-based
  authority attacks cannot reach live placement.
- Authority is checked again after pause/restart and before every batch.
- Marker rejection, collision, rail, water, representative mismatch, timeout,
  partial execution, audit mismatch, and abort stop later batches.
- A timed-out command enters unknown/audit state and is never blindly retried.
- Cleanup excludes unrelated entities, rails, markers, and nonmatching
  prototypes.
- Restart resumes or safely halts from every state without duplicate placement.
- Every automatic stop maps to one configured signal or exact audit condition;
  model judgment cannot waive or create placement safety gates.

### Acceptance check

After all mocked failure cases pass, perform a management-authorized staged live
validation: place and audit one representative marker/ghost at a confirmed safe
location, then exercise a tiny multi-batch design. Stop immediately on any
timeout or mismatch. Verify every expected live ghost before declaring success.

### Primary requirements

AUTH-002 through AUTH-006, GHOST-001 through GHOST-010, OPS-004, QUAL-001,
QUAL-003, QUAL-006.

## Required follow-up passes before final activation

First-pass or stub completion allows dependent prototype work to proceed but
does not transfer unfinished scope to Step 14. Before final activation, return
to each owning step and complete its recorded deferred items:

- Step 3 follow-up: continuous polling, missing-file/backoff behavior,
  replacement-during-read race hardening, source-time configuration, and large-
  log chunking.
- Step 4 follow-up: carefully scoped invocation variants, canonical decision
  records, runtime flag wiring, concurrent state locking, and greeting
  delivery/commit reconciliation.
- Step 5 follow-up: complete rendering, byte budgets, pagination, rich text/GPS,
  artifact/command content policy, Unicode hardening, retries, and delivery
  reconciliation. Post-Step-6 chat specifically reconfirmed duplicated reply
  prefixes, leaked Markdown markers, and overlong-response fallback behavior.
- Step 6 follow-up: model-directed state-needs planning over four locally
  validated read-only tools and per-player provenance context is complete and
  deployed. Still pending here are the remaining authoritative direct routes:
  historical state, authority declines, runtime self-description, and complete
  stale/partial/unavailable policy. Broad investigation belongs to Steps 10-11.

These are follow-up passes of Steps 3-6, not new Step 14 responsibilities. Their
timing will be reviewed separately after the prototype milestone.

## Step 14: Complete operations, end-to-end acceptance, and activation

### Scope

Harden the assembled full bot, run the complete acceptance suite, rehearse
rollback, and only then activate it publicly.

### Work

1. Add validated operator controls for status, start, stop, restart, public
   replies on/off, welcomes on/off/suppress, queue drain, health summary,
   placement status, and placement abort through the narrow project launcher.
2. Report log freshness, cursor lag, archive health, queue depth, provider/RCON
   state, renderer rejections, delivery failures, and active placement state.
   The model may summarize these measurements, but configured thresholds and
   exact outcomes remain authoritative.
3. Enforce bounded queues, per-player ordering, serial read-only RCON, serial
   delivery, and exclusive mutation placement.
4. Add failure containment for every external dependency and event type.
5. Verify that all required follow-up passes belonging to earlier steps are
   complete; do not implement their missing scope inside Step 14.
6. Run all requirement-level automated tests and map them to stable IDs.
7. Run the 25 initial acceptance scenarios from `FULL_BOT_REQUIREMENTS.md`,
   including the amended welcome instruction behavior.
8. Run staged provider, read-only RCON, rendering/delivery, welcome, restart,
   archive rebuild, and management-only placement smoke tests.
9. Rehearse rollback: stop admission, suppress greetings, drain/cancel safe
   work, preserve archive/state, and audit rather than auto-clean partial
   placement.
10. Update README and handoff documentation with setup, controls, boundaries,
   data retention, health, recovery, and known limitations.
11. Activate public replies only after explicit management approval. Retire or
    disable the POC listener so both bots cannot respond concurrently.
12. Keep health, rollback, queue admission, mutation leases, test pass/fail, and
    activation permission application/operator-owned; the model may explain
    evidence but cannot decide or override these outcomes.

### Tests

- Complete dependency-free suite makes no live provider or RCON call.
- Concurrent-player ordering and bounded admission under load.
- Provider, archive, renderer, queue, delivery, and RCON failure injection.
- Complete ASCII/Unicode/invalid-input, exact-byte-boundary, rich-text
  injection, trusted GPS, pagination, opaque-artifact, command-shaped follow-up,
  and exact-sent-text renderer fixtures.
- Restart/rotation/truncation deduplication and archive/index recovery.
- All 25 acceptance scenarios pass with evidence.
- Rollback rehearsal preserves data and prevents new output or mutation.

### Acceptance check

All automated and staged acceptance evidence is recorded; status and recovery
controls work; rollback is rehearsed; the POC listener is not concurrently
active; and `dlbattle` explicitly approves public activation. Only then is the
full bot declared released.

### Primary requirements

OPS-001 through OPS-005 and QUAL-001 through QUAL-006, plus the complete initial
acceptance suite and all requirements implemented and transitively verified by
their owning earlier steps.

## Cross-step decision gates

These choices are intentionally resolved when evidence becomes available:

- Across Steps 8-14, the model owns natural-language understanding, ambiguity
  resolution, comparison framing, tool/calculator/design planning,
  clarification wording, and answer synthesis. Local code is limited to
  authenticated identity/authority, typed schema and capability validation,
  authoritative lookup, deterministic calculation, bounded query compilation
  and execution, provenance, rendering safety, explicit operational thresholds,
  and controlled effects. Do not build semantic regex catalogs, fuzzy intent
  engines, prose classifiers, or question-specific handler trees.

- Step 2 records archive rotation thresholds. The first release uses a tagged
  UTF-8 text log plus small atomic flat-text state files and adds neither JSON
  storage nor SQLite.
- Step 5 measures and records the chat byte budget and pagination policy.
- Step 10 records read-only query step/object/byte/page/time bounds.
- Step 11 records first-release domain coverage and Factorio API limitations.
- Step 12 keeps raw model-authored placement Lua/RCON disabled unless a separate
  reviewed design decision proves it necessary and safe.
- Step 14 records the provider concurrency setting after ordered load tests.

None of these gates permits weakening the authority boundary, read-only
enforcement, placement validation, archive retention, or honest unknown/partial
result behavior.

## Completion record

Update this section after each completed step:

| Step | Status | Completion date | Evidence/decision summary |
|---|---|---|---|
| 1 | Complete | 2026-07-21 | Separate offline package, validated configuration, typed contracts/interfaces, 62-test suite passing. |
| 2 | Complete | 2026-07-21 | Tagged UTF-8 archive, atomic text state, retained 10 MB segments, reconstruction and migration tests; 79 tests passing. |
| 3 | First pass complete | 2026-07-21 | Durable complete-line reader, flat-text cursor, chat/join/leave normalization, archive-before-cursor ordering; 90 tests passing. |
| 4 | First pass complete | 2026-07-21 | Deterministic invocation/self-loop handling and durable welcome intents with required Jimbo instruction; 103 tests passing. |
| 5 | Minimal bridge complete | 2026-07-21 | One-line renderer, fixed-wrapper transport, serial archived delivery, welcome completion, live smoke confirmation; 113 tests passing. |
| 6 | Model planner live; other routes pending | 2026-07-21 | Four-tool model-directed state-needs planning, strict local validation, fixed read-only execution, provenance follow-ups, hosted/live smokes, and managed deployment; remaining direct routes stay attached to Step 6; 137 tests passing. |
| 7 | Complete/live | 2026-07-21 | Real Groq gateway, separated trusted context, three delivery-committed exchanges per player, hosted smoke, and active full-bot listener; Step 7 tests included in the 137-test suite. |
| 8 | Not started | - | - |
| 9 | Not started | - | - |
| 10 | Minimal core live; expansion pending | 2026-07-21 | Six-step catalog/schema validation, one correction retry, separate transport/model-context bounds, quota observability, fixed read-only execution, provenance, and adversarial rejection. |
| 11 | Platform + logistics slices implemented; other domains pending | 2026-07-21 | Platform identity/orbit/transit, cargo/requests/schedule plus targeted logistic provider/storage counts and scoped container inspection; 149 tests and harmless live smokes pass. |
| 12 | Not started | - | - |
| 13 | Not started | - | - |
| 14 | Not started | - | - |
