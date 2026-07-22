# Jimbo Full Bot Requirements

Status: requirements baseline ready for architecture design (2026-07-21)

This document defines the product and system requirements for the full Jimbo
Factorio server chatbot. It is derived primarily from `FULL_BOT_FINDINGS.md`
and the behavior proven by the completed POC. It does not authorize changes to
the POC and does not prescribe the full implementation architecture.

Normative terms use their usual meanings: **must** is required, **should** is a
strong preference that needs a recorded reason to omit, and **may** is optional.
Requirement IDs are stable references for design, implementation, and tests.

## 1. Product objective

Jimbo the Jr. Engineer must be a useful, interesting, socially comfortable
public-chat participant that gives useful Factorio answers, can investigate
broad live server state, and clearly describes its actual capabilities. The
language model may interpret the Jr. Engineer identity and supply the personality
rather than application code prescribing a detailed character script. Technical
capability enforcement and honest limitations take priority over producing a
fluent answer. Jimbo does not moderate player conduct: server owners and human
administrators decide what behavior is acceptable.

The full bot must preserve the proven public chat loop while replacing model
guesswork with deterministic or validated facilities where correctness or
technical operability requires it. Validation determines whether an operation
is supported and well formed; it must not judge whether player behavior is
acceptable.

## 2. Scope

### 2.1 In scope for the full bot

- Explicitly invoked public conversation with bounded conversational context.
- Non-Factorio conversation.
- Deterministic automatic welcome and welcome-back messages.
- Generic Factorio knowledge, calculations, and broad live game access through
  free-form model-authored Lua/RCON.
- Transparent per-player conversation and presentation preferences.
- Transparent handling of social prompts, corrections, commands, coordinates,
  and encoded artifacts without treating displayed text as executable input.
- A canonical, durable event archive and deterministic historical-event queries.
- Runtime-owned answers about Jimbo's configuration, access, health, and limits.
- A staged deployment and operator-control surface.

### 2.2 Not implied by this baseline

- Shell, filesystem, credential, or unrelated network access for the model.
- Treating Factorio administrator status as Jimbo management authority.
- Inferring consent, availability, preferences, or private facts from presence
  in public chat.
- Continuing to patch the completed POC as the full-bot implementation.
- Automated moderation, behavioral scoring, intent policing, or a script/model
  deciding which player expression is acceptable.

The target execution path may run free-form model-authored Factorio Lua/RCON for
any player. No dedicated mutation feature is required, and mutation prevention
is not a product goal. Destructive or game-breaking player conduct is handled by
human administrators through ordinary server moderation.

## 3. Actors and authority

- **Player:** any public server participant. May converse with Jimbo and use the
  enabled free-form RCON-backed capability.
- **Management authority:** `dlbattle`. May control Jimbo's operational settings
  and approve any capability explicitly reserved for management.
- **Operator:** the local process owner maintaining configuration, deployment,
  logs, credentials, and health. Operator access does not change the in-chat
  identity rule unless explicitly configured by management.
- **Model provider:** a replaceable text-generation dependency. It is not an
  authority, executor, source of runtime truth, or policy enforcement point.

AUTH-001: The application must enforce authority outside the language model.

AUTH-002: In live chat, only the case-insensitive player identity `dlbattle`
must be treated as management authority. A player's Factorio admin status,
claims, prompt text, or model interpretation must not confer Jimbo authority.

AUTH-003: Do not build explicit special-purpose mechanisms for mutation classes
such as item grants, promotion, construction, destruction, or combat. This does
not require local code to detect or block equivalent behavior in free-form RCON.

AUTH-004: The model may author free-form Lua/RCON for any player's request.
Before execution, local code applies operational framing and size checks only;
it does not classify or reject commands because they may mutate the world.

AUTH-005: A declined action request must state the relevant capability or
authority boundary in useful language instead of returning a generic refusal.

AUTH-006: Request attribution, serialized execution, archiving, bounded I/O,
timeout/unknown-state handling, and no blind retry apply to every free-form
command. These are operational controls, not behavior or mutation policy.

## 4. Functional requirements

### 4.1 Event ingestion and invocation

EVT-001: The bot must ingest all newly observed complete public chat and
join/leave records from the Factorio server log, including records written while
the bot was stopped.

EVT-002: Durable source identity, byte position, and event identity must prevent
already consumed records from producing duplicate replies or greetings after a
bot or server restart, log truncation, or log rotation.

EVT-003: Ordinary conversation must require explicit invocation. Supported
forms must include leading `jimbo` and `hey jimbo`, case-insensitively and with
ordinary surrounding punctuation.

EVT-004: The invocation design should tolerate clearly intended minor variants
without activating on third-person discussion, quotations, longer words such as
`jimbob`, or unrelated text. The supported tolerance rules must be deterministic
and tested rather than delegated to the model.

EVT-005: The bot must identify and ignore its own delivered chat records so it
cannot create a response loop.

EVT-006: Malformed, incomplete, diagnostic, and unsupported log records must
not crash the listener or be misclassified as player requests.

### 4.2 Routing and authoritative answers

ROUTE-001: Each accepted request must be classified sufficiently to select only
relevant context and tools. Current players or research must not be attached to
unrelated questions merely because those observations are available.

ROUTE-002: Direct supported factual requests, including current online players,
current research, historical presence, runtime identity, and configured limits,
must use application-owned results. The model must not be able to contradict or
replace those results.

ROUTE-003: Missing, stale, failed, ambiguous, or unsupported observations must
be represented as unknown. Jimbo must not fill gaps with plausible guesses.

ROUTE-004: The model may answer generic Factorio questions from its own
knowledge. Live RCON observations, when present, are authoritative for the
current server and must not be contradicted by generic model knowledge.

ROUTE-005: Community terminology and abbreviations such as `green modules` and
`EM` should be resolved using model knowledge plus recent conversation subject.
Material ambiguity should produce a concise clarification question.

ROUTE-006: Player-provided corrections must not silently become shared facts.
The bot may use a correction after validating it against an authoritative
source; otherwise it must label the claim as unverified and keep it from
contaminating later answers.

### 4.3 Factorio knowledge and calculations

KNOW-001: The language model is the primary source for generic information about
Factorio, including ordinary recipes, mechanics, strategies, and conversation.
The product accepts that this source can occasionally be mistaken; Jimbo should
express uncertainty when it is unsure rather than imply that every answer was
validated against game data.

KNOW-002: Current-world claims must come from RCON or another explicit live data
source. The model must distinguish generic game knowledge from observations
about this particular save, force, surface, or player.

KNOW-003: Ratio, throughput, crafting, module, power, and furnace calculations
must use a deterministic calculator with explicit inputs for item, recipe,
quality, machine, crafting speed, belt tier/throughput, modules, and game
version as applicable.

KNOW-004: A calculated answer must state the material assumptions and must ask
for clarification when different reasonable interpretations change the result.

KNOW-005: Comparative recommendations must distinguish relevant dimensions,
such as throughput, resource efficiency, power, pollution, space, and cost,
instead of silently converting `best` into one unstated metric.

### 4.4 Live server and historical state

STATE-001: Live access may use existing registered queries or model-authored
free-form Lua/RCON. Local code performs operational framing and size checks; it
does not require a restricted AST, allowlist, mutation detector, or behavioral
policy gate.

STATE-002: Current presence must be reported independently from historical
presence. A player's assertion must not override an authoritative current
snapshot.

STATE-003: The bot must support privacy-scoped deterministic queries for at
least joins, leaves, and previously seen players once the corresponding events
exist in the canonical archive. Death-history support is required only if the
log source provides reliable death events and the retention policy permits it.

STATE-004: Online status must not be described as AFK status, availability,
consent, willingness, or an assignment. Jimbo must not volunteer or order an
online player to perform work without that player's explicit participation.

STATE-005: Jimbo must ingest player map pings/tags as conversational observations
and may create useful map pings/tags itself. Observed coordinates retain their
source; generated coordinates are allowed but must not be falsely described as
queried observations.

STATE-006: Jimbo must have broad access to the current game state. The
intended capability is to answer any reasonable question that a player could
answer through laborious in-game observation, inspection, counting, and
cross-referencing, while removing that manual research burden.

STATE-007: The read-only system must support structured discovery, filtering,
projection, counting, grouping, aggregation, and relationship traversal across
game-state objects rather than requiring a dedicated hard-coded query for every
anticipated question.

STATE-008: Observable domains must include, where Factorio exposes the data:
surfaces and planets; forces and progression; players; entities and ghosts;
all player inventories and personal logistic requests without player-privacy
filtering; entity inventories, recipes, filters, requests, and control settings; logistic networks
and chests; trains, stations, schedules, and cargo; space platforms, hubs,
schedules, requests, and cargo; electric networks; production and consumption
statistics; pollution; resources; research; and map positions.

STATE-009: The system must support multi-step investigations that join facts
across domains. Examples include finding every logistic chest on Aquilo that
requests quantum processors, and determining which space platforms move which
resources from which origins to which destinations.

STATE-010: The model may use structured operations or free-form Lua/RCON. Prefer
a simple generate, execute, observe, and answer loop over a large proprietary
query language or semantic gate. Neither the model nor local code is responsible
for policing player conduct.

STATE-011: Execution should bound command and result size, support
pagination or incremental aggregation, and return explicit partial, timeout,
unavailable, or stale status. These are operational quality controls, not a
mutation-prevention or player-behavior boundary.

STATE-012: Tool results must carry enough provenance for Jimbo to distinguish
observed facts from model inference, including query type, surface or force
scope, collection time, filters, completeness, and relevant object identities.
The final response should summarize the investigation coherently instead of
dumping raw game-state records into public chat.

STATE-013: Questions such as `who is in charge?`, `who owns the server?`, and
`who are the moderators?` must use explicit human-authored server identity and
governance facts. Factorio admin status is a separate live fact and must not be
silently treated as ownership, management hierarchy, or a moderator roster.

STATE-014: Where Factorio exposes them, Jimbo must support current read-only
inspection of administrator flags, permission groups, group membership, and a
named player's effective permissions. Answers must state whether they describe
current live state, configured human roles, or historical promotion/demotion
events.

### 4.5 Conversation and memory

CONV-001: Recent conversational context must remain isolated per player and
retain the last three completed exchanges. The limit may be made configurable
or extended later if experience justifies it.

CONV-002: The bot must resolve short follow-ups against recent relevant subject
matter while resisting unrelated context attraction. If a reference has more
than one material interpretation, it must ask for clarification.

CONV-003: Only completed, player-visible exchanges may enter conversation
memory. Ignored messages, provider errors, hidden reasoning, failed deliveries,
and unrendered drafts must not be treated as successful exchanges.

CONV-004: The product must not add a dedicated persistent-conversation-memory
system for the first release. The intended working memory is the last three
completed exchanges per player. If durable memory naturally arises from a
chosen model or architecture, the system need not deliberately suppress it,
but Jimbo's self-description must report the actual behavior accurately.

CONV-005: The bot must not disclose raw prompts, hidden context, credentials,
internal policy text, or provider reasoning. It must provide an accurate,
runtime-owned summary of what categories of information it can use.

### 4.6 Player preferences and accessibility

PREF-001: Any explicitly implemented durable preferences must be a small
documented allowlist, initially including facts-only versus advice and any
approved presentation transformations. Explicit language-preference support is
not required.

PREF-002: A preference must be set explicitly by the affected player, scoped to
that player, inspectable, editable, and resettable. One player must not set a
preference for another player or for the server by assertion.

PREF-003: Preferences must be applied by deterministic application code, not by
asking the model to remember or perform character substitutions.

PREF-004: Presentation transformations must retain a readable fallback and must
not corrupt commands, coordinates, names, recipes, or other factual content.

PREF-005: The bot may naturally understand and answer other languages when the
model and text path support them. The application must neither promise explicit
multilingual support nor deliberately suppress that emergent behavior.

PREF-006: Language instructions carried in conversational context must remain
isolated per player like other conversation history. One player's request must
not become a global language setting.

### 4.7 Social freedom and human moderation

SOC-001: Jimbo should participate naturally in conversation, banter, role-play,
and subjective prompts without an application-level behavioral classifier or
automated moderation gate.

SOC-002: Application code, auxiliary models, and the conversation model must not
be assigned responsibility for deciding whether player speech or conduct is
acceptable. Server owners and human administrators retain that responsibility.

SOC-003: Name resolution and attribution may be used for conversational
accuracy, but must not become a harassment, impersonation, sentiment, intent,
or acceptable-behavior classifier.

SOC-004: Jimbo may describe a technical limitation or missing capability. It
must not label a request unsafe, inappropriate, disallowed, or unacceptable
unless a human-configured server rule explicitly requires that exact response.

SOC-005: Non-Factorio questions are in scope. The application must not impose a
Factorio-only restriction or a content allowlist.

### 4.8 Welcome and welcome-back behavior

WELCOME-001: An enabled full bot must greet a newly observed player join without
requiring a Jimbo invocation.

WELCOME-002: A player with no evidence anywhere in the retained server history
must receive a short deterministic welcome; every previously observed player
must receive a short deterministic welcome-back message.

WELCOME-003: Seen-player identity must be keyed case-insensitively while
retaining the latest display spelling. The minimum stored data must include the
identity and timestamps required for classification and deduplication.

WELCOME-003A: Seen-player memory is permanent for this server unless a human
explicitly deletes it. It must not expire after minutes, hours, days, bot/server
restarts, save changes, or the end of a particular play session.

WELCOME-003B: On initialization or migration, rebuild/seed seen-player state
from all available retained player evidence, including joins, leaves, and public
chat in the canonical archive and available server log. Historical evidence must
not emit retroactive greetings; it only determines welcome versus welcome back.

WELCOME-004: Routine greetings must not call the language model and must be
sanitized and sized for Factorio public chat.

WELCOME-005: Durable event identity must prevent duplicate greetings for the
same join record. No special reconnect grace period or reconnect-behavior tuning
is required; ordinary distinct join events may produce ordinary greetings.

WELCOME-006: Starting or restarting Jimbo while players remain online must not
emit greetings for historical or replayed joins.

WELCOME-007: Operators must be able to enable/disable welcomes and temporarily
suppress them during maintenance, staging, or bulk reconnect events.

WELCOME-008: Greeting behavior must not reveal previous join times, activity,
or other history beyond the neutral distinction between welcome and welcome
back.

WELCOME-009: Every welcome and welcome-back message must instruct the player to
begin queries with the word `Jimbo`. The instruction must remain short,
deterministic, and compatible with the supported `Jimbo` and `Hey Jimbo`
invocation forms.

Acceptance fixtures include returning players `itsnotyouitsme` and
`renard10177`, plus first-seen candidate `HANYUEYUE`, subject to the state store
present at full-bot launch.

### 4.9 Artifacts, displayed commands, and rich text

ART-001: Jimbo may discuss or display commands, Lua, RCON, shell text,
configuration, encoded payloads, and other executable-looking text. Displayed
text must remain data and must never enter an executor merely because a player
or model produced it. Execution requires a separately supported capability and
its explicit technical authorization path.

ART-002: Jimbo may generate and display blueprint strings and other artifacts
without deterministic generation or validation. If an artifact is used for live
placement, decode whatever fields are needed for that attempt and report whether
Factorio accepted it; do not claim validation that did not occur.

ART-003: Artifact text has the same message-length limits as other chat. Do not
add artifact-specific restrictions; if it does not fit, report the ordinary
transport limitation or paginate when practical.

ART-004: No command-shaped output filter is required. Initial and follow-up
requests may quote or restate executable-looking content; the separation between
chat rendering and executors is the control boundary.

ART-005: Advisory executable guidance should preserve its syntax and should be
described accurately. Version validation is useful when available, but lack of
validation is a correctness limitation rather than a behavioral prohibition.

ART-006: Model-authored Factorio rich text, GPS links, map tags, and pings may be
rendered. Preserve provenance so generated locations are not presented as live
observations.

### 4.10 Superseded ghost and blueprint placement requirements

The GHOST requirements below are retained for historical traceability but are
not active product requirements after DEC-009 (2026-07-22). They must not be
used to justify dedicated mutation mechanisms or mutation-prevention work.

GHOST-001: The first full bot release must be able to place entity ghosts and
complete blueprint designs as ghosts in the live game so construction bots can
build them. This capability is essential even though creating ghosts is a
deliberate game-state mutation.

GHOST-002: Every player may request live entity-ghost or blueprint-ghost
placement through chat. Factorio admin status and Jimbo management identity are
irrelevant to access to this capability; the execution record attributes the
request and result to the requesting player.

GHOST-003: The placement implementation may execute model-authored Lua/RCON after
lightweight checks for obvious truncation or mismatch with the requested ghost-
placement/deconstruction-marking task. The checks should catch likely model
mistakes without trying to provide perfect security or a complete formal parser.

GHOST-004: Prefer a structured design when convenient, but allow the model to
author placement Lua/RCON directly. Jimbo creates entity or blueprint ghosts,
not completed entities or directly placed tiles. Deconstruction requests use
Factorio deconstruction orders rather than direct removal. Do not add unrelated
mutation restrictions to this lightweight check.

GHOST-005: Before material placement, Jimbo should establish and report the
surface, anchor, orientation, and intended footprint and inspect obvious
collisions. Return observations to the model/requester and normally attempt
placeable ghosts rather than enforcing an all-or-nothing application policy.

GHOST-006: Placement must proceed incrementally. Validate representative ghosts
first, use small bounded batches, verify the live result after every batch, and
stop immediately on timeout, missing RCON response, unexpected entities, or
position mismatch. A timeout must be treated as an unknown outcome and audited
before any retry.

GHOST-007: Exact entity-center positions, directions, qualities, recipes,
filters, priorities, control behavior, wire connections, module requests,
mirroring, and other supported blueprint settings must be preserved and audited
after placement. The bot must not claim success from generated data alone.

GHOST-008: For live blueprint-derived placement, decode enough of the artifact
to attempt the requested ghosts and report parse or Factorio errors. Chunk-
aligned designs should preserve snapping, bounds, and grid offset. Remote
placement should use explicit positions rather than transforms observed to shift
designs on this server; perfect pre-validation is not required.

GHOST-009: The execution record must archive the requesting player, normalized
design, surface, anchor, footprint, validation results,
commands or command hashes, batch results, observed ghosts, failures, and final
status without recording the RCON credential.

GHOST-010: Any player may ask Jimbo to mark any described area or objects for
deconstruction, including areas unrelated to a prior Jimbo design. Use Factorio's
ordinary deconstruction-order mechanism and let construction bots perform the
work; do not directly delete entities or tiles or impose an application-owned
scope policy.

## 5. Response and renderer requirements

RENDER-001: Public responses must fit the configured Factorio chat budget before
delivery and end on a complete word and preferably a complete sentence.

RENDER-002: The renderer must remove only transport-breaking control characters,
normalize unsupported Unicode predictably, enforce line/byte limits, and detect
obvious repeated-generation loops. Markdown and rich text are expression, not
behavior violations; preserve them when the transport supports them.

RENDER-003: Observed structured values and generated text must retain provenance,
but both may use rich text. Transport normalization must not silently corrupt a
command or artifact and leave it looking valid, and neither path may execute
displayed text.

RENDER-004: Long lists must be summarized or paginated deliberately rather than
crowding out the answer or being cut mid-list.

RENDER-005: The archive must retain both raw model output and the exact
player-visible output, along with machine-readable transformation reasons.

RENDER-006: Questions about rendering limits or transformations must be answered
from renderer configuration and recorded behavior, not model introspection.

RENDER-007: The system must define and test one end-to-end text-encoding contract
covering Factorio log bytes, ingestion, archive storage, model requests and
responses, sanitization, PowerShell/RCON transport, and Factorio display.

RENDER-008: Valid supported Unicode must survive that path unchanged. Invalid
decoding or likely mojibake must be detected and recorded rather than silently
presented to the model as player text.

RENDER-009: When a requested language or script cannot be rendered reliably in
Factorio, the application must use a documented readable transliteration or
configured fallback language and explain the limitation from runtime metadata.

## 6. Runtime self-description and operations

SELF-001: Answers about model/provider identity, deployed Factorio version,
enabled tools, data sources, context, memory, retention, permissions, health,
renderer behavior, context/output limits, and observed token usage or remaining
provider quota must be assembled from current configuration and instrumentation.
Cost or quota disclosure is a human configuration choice, not a model guess or
an application-defined behavioral rule; credentials are never part of the
answer.

SELF-002: The model must not claim access to chat, logs, history, private data,
tools, or actions that the runtime has not explicitly exposed.

SELF-003: Jimbo must answer common identity and provenance questions from
runtime-owned facts: who/what Jimbo is, who operates the project, which model is
active, how an answer was obtained, which tools and live domains are available,
whether it learns or remembers across turns/restarts, and which revision is
deployed. Unknown model internals such as an undisclosed parameter count must be
reported as unknown rather than replaced with a guess about another model.

OPS-001: Implementation, staging/smoke validation, and public activation must
be distinct operational states. A revision must not answer public players until
its release is intentionally activated.

OPS-002: Operators must have controls for status, start, stop, restart, public
reply enablement, welcome enablement/suppression, and safe diagnostic checks.

OPS-003: Routine automated tests must not contact a live model provider or the
Factorio server unless explicitly marked and invoked as live tests.

OPS-004: Provider, tool, archive, renderer, queue, and delivery failures must be
observable without exposing credentials or silently switching to a known
unreliable behavior.

OPS-005: Provider/model choice must remain replaceable and must not weaken
locally enforced authority, validation, rendering, or archive guarantees.

OPS-006: When an active bot implementation is replaced by a new revision, the
new revision must announce itself in public chat and briefly summarize its
current player-facing capabilities and material limitations.

## 7. Canonical archive and privacy

ARCH-001: The full bot must maintain one append-only, self-contained canonical
event archive so later behavioral analysis does not require correlation with
`server-console.log`.

ARCH-002: The archive must record every newly ingested complete public chat and
join/leave event, including non-invocations, with source time, ingestion time,
player identity, source file identity and byte offset, monotonic sequence, and
versioned schema identity.

ARCH-003: For an invoked request the archive must additionally record acceptance
or rejection and reason, selected context and safe tool results, raw model
output, exact rendered output, transformations, delivery attempt, and result.

ARCH-004: Events must be flushed immediately. Rotation must be timestamped and
non-destructive. For the current single-server deployment, all canonical chat
archives must be retained without an archive-size target.

ARCH-005: The archive must never contain API keys, RCON credentials, environment
dumps, credential-bearing headers, or unrelated local secrets.

ARCH-006: The current deployment must archive all public chat for the life of
the single-server project. If Jimbo is distributed more widely, archive size,
retention, access, deletion, and privacy policy must be revisited before that
broader deployment.

ARCH-007: Durable seen-player and preference state must have documented schemas,
atomic updates, restart recovery, and migration/version handling.

## 8. Quality attributes

QUAL-001: One malformed event, failed tool, provider error, renderer rejection,
or delivery failure must not terminate the long-running listener.

QUAL-002: Requests from concurrent players must preserve player identity,
history isolation, ordering rules, bounded queueing, and rate limits.

QUAL-003: Every external dependency and live query must have a timeout and a
bounded failure path. Unbounded retries are not permitted.

QUAL-004: The system must preserve credentials using the repository's existing
machine-local secret and fixed RCON credential flows.

QUAL-005: Requirement-level tests must cover deterministic routing, authority,
state, calculations, rendering, archive behavior, restart/replay safety,
preferences, welcomes, and failure modes without consuming hosted quota. Live
RCON integration is permitted when it materially verifies Factorio behavior.

QUAL-006: The free-form execution path must have staged operational validation.
Tests need not prove read-only behavior or introduce one information category at
a time.

QUAL-007: Hosted model calls must be paced against observed provider request and
token limits. A provider `429` must not trigger an immediate second hosted model
call or a blind retry. Jimbo must return a short locally generated, player-visible
temporary-rate-limit response, preserve the failed request in the archive, and
remain available for later requests. Operator-led live test sequences should
normally leave 20-30 seconds between model-backed queries and pause about one
minute after a `429`, unless current provider telemetry supports a different pace.
Within one ordinary request, the required planning and synthesis calls must be
separated by a short delay; the initial implementation uses two seconds.

## 9. Initial acceptance scenarios

Any ghost/placement scenarios retained in this historical acceptance list are
superseded and are not release gates. General free-form execution is tested for
operational behavior without deliberately exercising destructive mutations.

The detailed acceptance suite will map requirements to automated or staged
tests. At minimum, the full bot is not ready for public activation until these
scenarios pass:

1. `Who is online?` returns the fresh authoritative list even if the asking
   player falsely claims that an online player is absent.
2. A request about belt choice does not receive an unrelated player list or
   research snapshot.
3. `green modules in miners` resolves or clarifies module identity rather than
   confidently answering the wrong interpretation; generic effects may come
   from the model and should be framed with appropriate uncertainty.
4. `what about EM` after a machine discussion resolves to the electromagnetic
   plant or asks a focused clarification; it does not switch to elevated rails.
5. A demolisher recommendation accounts for validated damage resistances and
   never recommends a fully resisted damage type as the core strategy.
6. A subjective `best` question states the comparison dimensions or asks for
   the player's goal.
7. A furnace-count calculation identifies the belt tier and assumptions and is
   reproduced by the deterministic calculator.
8. A request for a blueprint or encoded artifact may yield model-generated text
   subject only to the ordinary message-length path. Jimbo states whether it was
   actually decoded, accepted by Factorio, or merely generated.
9. A request to emit `/promote`, Lua, or a console command may produce that text
   in public chat, including on a follow-up. The text is archived and rendered
   but never routed to an executor without a separate supported and authorized
   execution request.
10. Jimbo can read player pings/tags and create its own useful map pings/tags;
    it distinguishes observed coordinates from generated suggestions.
11. Any player can request validated ghost or blueprint-ghost placement for bots
    to build. The request is attributed to that player and does not depend on
    Factorio admin or Jimbo management status. Other mutation classes remain
    outside the currently implemented capability set.
12. Banter and role-play reach the conversation model without an application or
    auxiliary-model moderation decision; human administrators remain responsible
    for judging player behavior.
13. A player's explicit facts-only preference affects only that player, can be
    inspected and reset, and survives restart only according to the approved
    retention policy.
14. First-ever observed player, later join, reconnect churn, and bot restart produce exactly the
    required welcome/welcome-back behavior without greeting bursts, and every
    delivered greeting tells the player to begin queries with `Jimbo`.
14a. A player seen in pre-launch chat or leave history, such as Moon-O-Cronic,
     receives `Welcome back` on the first join processed by the full bot.
15. Jimbo accurately reports its actual provider/model, memory, archive scope,
    read-only tools, action restrictions, and renderer limits without exposing
    its raw prompt or credentials. Cost/quota figures follow the configured
    human disclosure choice.
15a. Jimbo distinguishes `dlbattle` as the configured owner/management contact
     from the live Factorio administrator list; reports whether a separate
     moderator roster is configured; and can inspect a named player's current
     admin flag, permission group, and effective permissions when available.
15b. Jimbo accurately explains how it obtained a live answer, whether it learns
     or remembers, its deployed revision, context/output limits, and observed
     token/quota figures. It never substitutes GPT-4 or invented parameter counts
     for unavailable model metadata.
16. The canonical archive alone reconstructs a request from source event through
    routing, tool use, raw generation, rendering, and delivery while containing
    no secrets.
17. A Swedish conversational instruction for one player leaves another player's
    replies unaffected and expires naturally with that player's bounded history;
    no explicit multilingual preference subsystem is required.
18. When the model naturally accepts Swedish text containing `å`, `ä`, and `ö`,
    the general text path either round-trips it correctly or uses the documented
    transliteration fallback without mojibake.
19. A production-time calculation uses target count, existing count, recipe
    time, products per craft, machine crafting speed, and relevant modifiers
    with units; correcting any input causes the entire result to be recomputed.
20. `Which logistic chests on Aquilo request quantum processors?` discovers the
    applicable surface and logistic chests, filters their configured requests,
    and returns a complete attributable result without a hard-coded
    quantum-processor-specific query.
21. `Which ships are bringing what resources from where and to where?` joins
    platform identity, schedule or route, origin/destination, cargo or logistic
    requests, and current status into a coherent answer with collection time and
    explicit limitations where route intent cannot be proven from current state.
22. A broad query over a large surface remains operationally bounded, reports
    pagination, timeout, or partial coverage honestly, and does not materially
    stall the dedicated server.
23. Superseded: `dlbattle` can ask Jimbo to design and place a bot-buildable layout at a
    confirmed location; Jimbo reports the surface, anchor, footprint, and
    preflight result, places a representative test ghost and then bounded
    batches, and audits every expected ghost and critical setting.
24. Superseded: the same placement request from any other player follows the same design,
    confirmation, placement, and audit workflow and can produce live ghosts.
25. Superseded: a placement timeout causes an audit before retry. Likely syntax/API mistakes
    are returned for model correction; ghost placement does not silently become
    direct construction or direct tile placement.

## 10. Product decision register

Resolved decisions:

- DEC-001: Non-Factorio conversation is in scope. Jimbo should be interesting to
  talk to. No application code or model is designated as a moderator of player
  behavior; human administrators make those decisions.
- DEC-002: Jimbo is **Jimbo the Jr. Engineer**. The model may decide what that
  means in conversational personality; no detailed scripted persona is needed.
- DEC-003: Retain the last three completed exchanges per player. Do not build a
  dedicated durable conversation-memory feature, but do not suppress durable
  memory that naturally arises from the selected architecture.
- DEC-004: Archive all canonical chat for the current single-server project.
  Revisit size and retention only before materially wider distribution.
- DEC-005: Do not explicitly support additional languages. Allow multilingual
  behavior to arise naturally and do not suppress it; keep context isolated per
  player and maintain a generally correct text-encoding path.
- DEC-006: Do not design or tune a welcome reconnect grace period. Prevent exact
  replay duplicates and otherwise let normal join handling behave naturally.
- DEC-007: The model is the primary source for generic Factorio information.
  RCON is authoritative for the state of the current live game.
- DEC-008: Give Jimbo broad RCON-backed access intended to answer any
  reasonable question a player could answer through laborious in-game research.
  Support composable structured investigation across entities, logistics,
  trains, platforms, surfaces, forces, statistics, inventories, schedules, and
  relationships rather than limiting release scope to a short canned tool list.
- DEC-008A: The data itself is not confidential from players. Avoid a large
  proprietary query language that must be retaught in every prompt. Keep current
  registered operations as a reliable fallback, but allow direct model-authored
  Lua/RCON with operational framing, serialization, size, attribution, archive,
  and timeout controls. Do not add mutation or behavioral classification.
- DEC-008B: Registered/custom adapters are disposable fallback aids. When an
  adapter creates routing, schema, maintenance, or answer-quality problems,
  prefer eliminating or bypassing it for free-form RCON instead of repairing it
  solely to preserve category-specific infrastructure.
- DEC-009: Do not create dedicated mutation mechanisms. Free-form RCON may
  incidentally mutate the world; human admins handle destructive or
  game-breaking player conduct through ordinary moderation.
- DEC-010: Artifact delivery uses the ordinary chat message-length path with no
  additional blueprint/encoded-content restriction.
- DEC-011: Credentials are never disclosed. Public cost, usage, and quota detail
  follows an explicit human-configured disclosure setting; Jimbo must not invent
  unavailable figures.
- DEC-012: Do not optimize or set a formal service target for response latency.
  Observed latency has not been a problem; anything from effectively immediate
  through roughly one minute is acceptable for now.
- DEC-013: Use an append-only UTF-8 text event log plus small, documented,
  atomic flat-text state files for the first release. The archive may use a
  minimal tagged line format but does not need JSON or SQLite. Add structured
  storage only if later evidence demonstrates a concrete need. The flat-file
  approach must still satisfy restart recovery, deduplication, format
  versioning, migration, archive reconstruction, and privacy requirements.
- DEC-014: Reuse the existing ignored machine-local Groq API key file. Full-bot
  implementation must not require a new key or require the user to re-enter,
  relocate, print, or recommit the existing key. Offline configuration and
  tests must not validate the key by making a live provider call.
- DEC-015: Full Bot Step 7 must integrate and exercise real Groq model calls
  through the existing key file; a stub-only or placeholder model integration
  does not satisfy that implementation pass. Routine automated tests remain
  mocked and must not consume hosted quota, followed by an explicit bounded
  hosted smoke test.

There are currently no unresolved product-scope decisions in this register.
Detailed privacy, query-budget, and implementation choices remain architecture
work rather than reasons to narrow the broad read-only product requirement.

## 11. Evidence traceability

`FULL_BOT_FINDINGS.md` remains the detailed evidence record. This baseline maps
its priority groups as follows:

- Findings priorities 1-3, 6-7, 11-12, 19-20, and 23 -> ROUTE, KNOW, STATE,
  CONV, and SELF requirements.
- Priorities 4, 13-15, 17, 21-22 -> AUTH, SOC, STATE, and ART requirements.
- Priorities 5, 10, and 24-27 -> RENDER, ART, and PREF requirements.
- Priorities 8-9 and 16 -> SOC, PREF, and OPS requirements.
- Priority 18 -> ARCH requirements.
- Requested welcome behavior -> WELCOME requirements and acceptance scenario 14.

The 45 representative findings remain available for a future case-level
traceability matrix if implementation verification needs it. Product-scope
decisions are sufficiently resolved to begin the full-bot architecture and
design document. The design should reference these stable requirement IDs and
record any discovered conflict or necessary requirement change explicitly.
