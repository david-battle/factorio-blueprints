# Jimbo bot cold-start handoff

Read this file first after a new Codex session. Then read
`FULL_BOT_REQUIREMENTS.md`, which is the normative input to the architecture
phase, followed by `FULL_BOT_FINDINGS.md` for the player-testing evidence behind
it. Read `POC_PLAN.md` only when detailed POC history or numbered-step decisions
are needed; it is authoritative but intentionally long.

## Current state (2026-07-21)

- POC Steps 1, 2, 3, 4, 5, 5.5, 5.75, 5.8, and 6 are complete.
- Full Bot Step 1 is complete. The separate `jimbo_full_bot` package has an
  offline-only shell, validated configuration, typed contracts/interfaces, and
  18 Step 1 tests.
- Full Bot Step 2 is complete. It adds the tagged UTF-8 archive, retained 10 MB
  segments, atomic flat-text state, integrity/migration behavior, and 17 Step 2
  tests.
- Full Bot Step 3 has a completed first pass: durable
  complete-line reading, flat-text cursor resume, source/byte event identity,
  verified chat/join/leave normalization, archive-before-cursor ordering, and
  11 tests. The active full-bot listener uses this reader against the live log.
- Full Bot Step 4 now includes retained-history seen-player reconstruction:
  deterministic leading invocation, self-loop suppression, durable seen-player
  classification seeded from archived/current-log chat, join, and leave evidence,
  restart-safe welcome intents, and the required `Jimbo` instruction in every
  greeting. Historical reconstruction emits no greetings; later live joins by
  known players receive `Welcome back`.
- Full Bot Step 5 has a completed minimal delivery bridge: one-line plain text,
  length fallback, inert Lua containment, fixed-wrapper transport, serialized
  archived outcomes, deduplication, and confirmed welcome completion. The live
  renderer now transliterates unsupported Unicode to readable ASCII before RCON.
- Full Bot Step 6 is complete. In addition to model-directed live-state
  planning, it has application-owned runtime/server identity, philosophy,
  retained player-history, current Factorio admin-list, and named-player
  permission facts. These answers are formatted locally, identify `dlbattle`
  as server owner and Jimbo operator, distinguish live admin flags from
  ownership/moderation, and preserve unknown/unavailable outcomes without
  model guessing.
- The Step 6 live-routing correction is implemented and deployed. Planning now
  classifies one or more validated subjects (jimbo, server, server_owner,
  factorio_admins, named_player, or other) and local validation requires
  compatible facts, rejects wildcard player identities, distinguishes connected
  admins, and reports Jimbo's real no-kick/no-ban boundary. The quota-free suite
  has 161 passing tests. PID 25012 started cleanly and the revision was announced
  publicly; a bounded player-driven live-question smoke remains the final
  acceptance check.
- A basic Step 6 live-state follow-up is deployed. Deterministic local phrases
  route connected-player, current-research/progress, game-time, and available-
  surface questions to one fixed read-only RCON snapshot and direct formatter;
  the model never chooses RCON. Three tests bring the suite to 131. The live
  query smoke passed, the listener was restarted and verified as PID 9056, and
  the revision was announced publicly. This deterministic path is now retained
  only as the fallback described below.
- The model-directed Step 6 state-needs follow-up is implemented and deployed.
  One strict planning call selects only four approved
  read-only operations; local code validates and executes a fixed snapshot, and
  one synthesis call receives provenance-bearing results. The phrase matcher is
  fallback-only in the new runtime path. Hosted planning and harmless live RCON
  smoke checks passed without public delivery. The managed listener was
  restarted and verified running as PID 17992, and the revision was announced
  publicly under OPS-006. Always query status rather than trusting this PID.
- Steps 10 and 11 now have a deployed minimal vertical slice. The model selects
  up to six schema-validated operations; trusted local code returns platform
  identity/status/location, hub cargo and item counts, logistic requests, and
  schedules from a fixed read-only query with provenance. Generic query
  primitives and every non-platform domain remain pending. Hosted and harmless
  live smokes passed, and the managed listener was activated as PID 24400.
  Always query status rather than trusting this PID.
- The next Step 11 slice is implemented and deployed (always query status for
  the current PID):
  logistic-network identity and position, robot availability/totals, roboport
  and chest-member counts, network item totals, and bounded logistic-container
  inventory/request inspection. It uses four registered operations and split
  fixed read-only templates to stay under the RCON command-length limit. Bounds
  are 32 networks, 128 item rows per network, 64 containers, and 32 rows per
  container; warnings make results partial rather than exhaustive.
- A quota-safe logistics breadth iteration adds direct exact-item counts for
  all members, providers, or storage; exact-item requester/container inspection
  is scoped before a 128-relevant-container bound. Plans may use six read-only
  steps and receive one schema-correction retry. Prior observations are
  compacted to 8,000 characters and current model-visible tool data is capped
  at 16,000 characters independently of the 200 KB RCON transport guard.
  Provider token usage and safe remaining-quota headers are archived when
  available. Live no-public smokes found 504 provider-available steel plates
  and 101 steel plates physically in requester chests in Nauvis network 2.
  The managed listener was restarted as PID 10704; always query status rather
  than trusting this recorded PID.
- Platform whereabouts now distinguish the internal `platform-N` surface from
  a stopped orbital location or transit connection. Hosted/live smoke correctly
  reported Froidulant stopped in orbit at Nauvis. Exact trusted rich-text-only
  platform names may render as Factorio icons; all model-authored tags remain
  inert. This incorporates morganc's live rendering demonstration.
- The deployment was announced publicly as required. This is a standing rule:
  every new in-game testing iteration announces its capabilities and relevant
  limitations in public chat after activation.
- Announcements describe player-visible capabilities only. Do not advertise
  general RCON command availability; free-form RCON is a hidden internal
  implementation detail.
- Live player testing found that the safe renderer stripped the square brackets
  from a rich-text platform display name, making the literal answer ambiguous.
  The renderer now spells those unsafe delimiters as `left-bracket` and
  `right-bracket`, while still preventing Factorio rich-text interpretation.
- Full Bot Step 7 is complete and deployed as the playable prototype. It adds
  the real Groq gateway using the existing ignored key, separated provider
  messages, three delivery-committed exchanges per player, and live
  ingestion-to-RCON orchestration. Nine new tests bring the complete suite to
  128 passing tests. A hosted local-only smoke passed, and the managed listener
  was switched from the POC to the full bot.
  The replacement was announced publicly with its capabilities and current
  limitations; OPS-006 requires the same for later active revision changes.
- Unfinished first-pass scope remains attached to its original step. Step 3,
  Step 4, Step 5, and Step 6 each have a recorded follow-up pass; do not move
  that work into Step 14. Step 14 integrates, validates, and activates only
  after the owning-step follow-ups are complete.
- Step 7's real Groq path and hosted smoke are complete. Routine automated tests
  remain mocked and quota-free.
- The complete combined suite has 170 dependency-free tests. Automated
  model/provider tests remain mocked and consume no Groq quota. Tests may invoke
  live RCON when authoritative Factorio execution is materially useful.
- The POC is declared proven. Do not add more ambitious POC features; the next
  phase is a separate full-chatbot design.
- Player testing findings through the original supplemental 15:18:03 server-time
  cutoff plus the scoped post-Step-6 18:03-18:05 platform investigation are
  captured in `FULL_BOT_FINDINGS.md`. The newer evidence shows that platform
  surface identity is insufficient for display-name and cargo questions.
- `FULL_BOT_REQUIREMENTS.md` is complete enough to begin architecture design. It
  contains stable requirement IDs, 25 initial acceptance scenarios, and a
  resolved product-decision register.
- The full-chatbot architecture draft is in `FULL_BOT_DESIGN.md`, and the
  fourteen-step serial implementation roadmap is in `FULL_BOT_PLAN.md`. Do not
  turn individual findings into more POC prompt patches.
- The next live-state expansion continues Step 10's generic investigation
  primitives and Step 11 beyond the now-live platform-first vertical slice.
  Current platform coverage distinguishes display name from internal surface
  identity and adds bounded hub cargo, item filtering, requests, schedule,
  location, and status.
  Do not build a local intent taxonomy: the model proposes structured plans;
  local code owns the capability catalog, validation, fixed queries, bounds,
  provenance, and execution. Remaining domains stay pending in Step 11.
- Steps 8-14 were audited for unwanted local intelligence. The recorded design
  now assigns preference/calculation/investigation/design intent, ambiguity,
  clarification, comparisons, and synthesis to the model. Local code is limited
  to ownership/authority, typed validation, authoritative candidate lookup,
  deterministic arithmetic, bounded execution, provenance, rendering safety,
  explicit measured operational thresholds, and controlled effects. Do not add
  semantic regex catalogs, fuzzy intent engines, prose classifiers, or
  question-specific handler trees.
- An experimental Step 10 model-authored free-form Factorio Lua/RCON path is
  implemented and deployed for every player. One planning pass may emit one
  bounded physical command line; the fixed wrapper executes it serially, restores
  the shared command file, archives attribution/command/result, and one synthesis
  pass interprets the result. It times out without retry and has no mutation or
  behavior classifier. Live player-driven capability testing remains pending.
  Existing adapters are disposable fallback/reference code: remove or bypass a
  troublesome adapter rather than repairing it solely to preserve categories.
- Jimbo is Jimbo the Jr. Engineer. Non-Factorio conversation is in scope, and
  the model may supply the detailed conversational personality without being
  assigned server-moderation responsibility.
- Keep the last three completed exchanges separately per player. Do not build a
  dedicated persistent conversation-memory system, but do not deliberately
  suppress persistence that naturally arises from the eventual architecture.
- The model is the primary generic Factorio knowledge source. Broad RCON-backed
  investigation is authoritative for this live game and should answer
  questions that players could otherwise resolve through laborious inspection.
- Do not create dedicated mutation features for ghost placement, deconstruction,
  item grants, promotion, construction, destruction, or combat. Free-form RCON
  may incidentally mutate the world; human admins handle destructive or
  game-breaking player conduct through ordinary moderation. Former dedicated
  placement Steps 12-13 are superseded and are not activation blockers.
- Archive all public chat for this single-server project. Long-artifact delivery,
  a cost/quota dashboard, formal latency optimization, explicit additional-
  language support, and welcome reconnect-grace tuning are out of scope.
- The live bot uses Groq `openai/gpt-oss-120b`, with no automatic Ollama
  fallback. The local Ollama/Qwen path remains implemented but was too weak for
  reliable Factorio answers.
- Step 5.8 requires leading `jimbo` or `hey jimbo`, keeps the last three
  completed exchanges separately per player in memory, and sends structured
  history. Memory is deliberately lost on restart.
- The Groq key is machine-local at `runtime/groq-api-key.txt`. The entire
  runtime directory is ignored. Never print, transcribe, or commit the key.

## Listener operations

Change only `tools/jimbo-action.json`, then run the exact fixed launcher from
the repository `AGENTS.md`. Supported actions are:

- `{"action":"status","arguments":[]}`
- `{"action":"start","arguments":["--full-bot"]}`
- `{"action":"stop","arguments":[]}`
- `{"action":"restart","arguments":["--full-bot"]}`
- `{"action":"test","arguments":[]}`
- `{"action":"bot","arguments":["--full-bot"]}` for a foreground run

`start`, `stop`, and `restart` use `runtime/jimbo.pid`, avoiding approval for
changing process IDs. At this handoff, the full-bot listener is running and the
action file is left on `status`; always query status rather than trusting a
recorded PID. Listener stdout/stderr, full-bot state, and the canonical text
archive are under ignored `runtime/` paths.

## Important behavior and boundaries

- Project philosophy: maximize player freedom. Human owners and administrators,
  not application scripts, Jimbo's conversation model, auxiliary classifiers,
  or Codex, decide what player behavior is acceptable. Do not add automated
  moderation, behavioral scoring, intent/sentiment policing, harassment or
  impersonation classifiers, or acceptable-content gates. Keep this separate
  from operational execution controls, credential protection, protocol
  integrity, and the rule that displayed text is never
  executed merely because it appeared in chat.
- Seen-player memory for welcome-back classification is permanent for this
  server. Seed it from all retained join, leave, and public-chat evidence, not
  only joins processed after full-bot launch; historical reconstruction must not
  emit greetings.
- Do not volunteer, design, or implement new security features unless `dlbattle`
  explicitly asks for that specific feature. This includes restrictions around
  Lua or RCON execution. When planning unrelated capabilities, record only the
  minimum technical behavior needed for the requested feature and do not add
  speculative hardening as an automatic companion task.
- Current live-state selection prefers the deployed model-authored free-form
  Factorio Lua/RCON path, while validated registered operations and a fallback
  phrase matcher remain available.
  Existing registered operations remain disposable fallback/reference paths.
- Unrelated public chat is not sent to Groq. Only explicit leading invocations
  are processed.
- `dlbattle` is the management authority for bot operations. Every player may
  use the same free-form RCON-backed request path; conduct remains a human-admin
  moderation concern.
- Automated model/provider tests must not consume Groq quota. Tests may invoke
  live RCON when needed, using the fixed wrapper and normal operational controls.
- A repeated CLI `--prompt` sequence exists for console-only contextual smoke
  tests. Do not add `--send-to` when using multiple prompts.
- The full-bot canonical archive is `runtime/full-bot-archive/events.log` with
  retained numbered segments. Factorio's raw chat remains in
  `D:\factorio-server\server-console.log`; server-generated `game.print` replies
  are visible in the canonical archive even when absent from the console log.
- Never reset, truncate, or discard either log. Players are continuing to use
  the live full bot and later conversations may be useful design evidence.
- The old POC transcript remains append-only historical evidence. The new
  full-bot archive records all ingested public chat/join/leave events plus model,
  tool, render, and delivery lifecycle records.
- The findings cutoff is not a log-retention boundary. Chat after the cutoff
  remains available for a later review; do not scrape or summarize it unless
  the user asks.

## Working tree and next action

The POC implementation, findings, and requirements baseline are committed on
`main`. This handoff is being committed with the full-bot architecture and
roadmap, Steps 1-7, the model-directed Step 6 planner and subject-routing
correction, Step 10's experimental free-form RCON path, Step 11's
platform/logistics adapters, quota-safe breadth changes, and 170 tests. Verify
the working tree and latest commit after restart.
Earlier relevant commits are:

- `85bd820 Complete Jimbo chatbot proof of concept`
- `bf3e27b Capture Jimbo full bot design findings`
- `552503f Capture additional Jimbo player findings`

The user-facing `README.md` documents setup, operation, testing, diagnostics,
boundaries, and current limitations.

### Latest quota handoff (2026-07-22)

- The managed full listener was running as PID 17040 at handoff; always query
  status rather than trusting the recorded PID.
- Step 10's experimental model-authored live-query path is deployed. Planning
  and synthesis are separated by two seconds. A Groq `429` now ends that player
  request immediately, makes no second hosted call, and delivers a local visible
  temporary-rate-limit response.
- The complete dependency-free suite passes 170 tests. The final live test
  confirmed the new `429` behavior and did not reach RCON execution because the
  planning call itself was rate-limited.
- Groq's published free allowance for `openai/gpt-oss-120b` is 8,000 TPM and
  200,000 TPD. Today's archive records 114 successful calls and 126,249 tokens,
  but undercounts schema-correction calls, hosted development smokes, failures,
  and any other project/key usage. Minute-limit exhaustion was directly visible;
  persistent first-call `429`s after idle time strongly suggest the daily token
  allowance was later exhausted.
- Next small task: safely capture and archive Groq's `retry-after`, limit/reset
  headers, and bounded non-secret 429 detail so TPM versus TPD exhaustion and
  the actual recovery time are authoritative. Do not retry merely to diagnose.
- After quota recovers, repeat one live information question and inspect the
  archived generated command, observed result, synthesis, timing, and delivery.
  Do not advertise general RCON availability publicly; it is an internal detail.

### Remaining-step summary

1. Complete.
2. Complete.
3. Finish polling, missing-file recovery, read races, timestamps, and log chunking.
4. Finish invocation variants, greeting reconciliation, and permanent seen-player reconstruction from retained chat/join/leave history.
5. Finish byte budgets, pagination, Unicode/rich text, artifact delivery, retries, and delivery reconciliation.
6. Complete.
7. Complete/live.
8. Add durable per-player response/presentation preferences.
9. Add deterministic recipes, throughput, power, module, and ratio calculations.
10. Live-test and refine the deployed permissive model-authored Lua/RCON path; add safe 429 reset telemetry and retain registered tools only while useful.
11. Validate broad live-information coverage through free-form queries; add or repair specialized adapters only when repeated evidence justifies them.
12. Superseded; do not build a dedicated mutation-design subsystem.
13. Superseded; do not build a dedicated placement/deconstruction subsystem.
14. Finish operations, tests, acceptance, rollback rehearsal, documentation, and activation.

## Fresh-session checklist

1. Read this file, `FULL_BOT_REQUIREMENTS.md`, and `FULL_BOT_FINDINGS.md`.
2. Run `git status` and preserve any user changes.
3. If touching the live bot, query listener status through the fixed project
   launcher before assuming its state.
4. Do not clear runtime files or the Factorio server console log.
5. Treat chat after the latest recorded findings cutoff as uncaptured evidence unless
   the user explicitly requests another review.
6. Review `FULL_BOT_DESIGN.md` and `FULL_BOT_PLAN.md`, then begin the requested
   numbered full-bot step as a separate project phase; do not reopen the POC
   merely because the desired full bot needs more capabilities.
