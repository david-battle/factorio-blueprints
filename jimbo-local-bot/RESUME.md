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
- Full Bot Step 4 has a completed first pass sufficient for Steps 5-7:
  deterministic leading invocation, self-loop suppression, durable seen-player
  classification, restart-safe welcome intents, and the required `Jimbo`
  instruction in every greeting. It adds 13 tests.
- Full Bot Step 5 has a completed minimal delivery bridge: one-line plain text,
  length fallback, inert Lua containment, fixed-wrapper transport, serialized
  archived outcomes, deduplication, and confirmed welcome completion. The live
  renderer now transliterates unsupported Unicode to readable ASCII before RCON.
- Full Bot Step 6 is a completed stub sufficient for Step 7: accepted
  invocations become tool-free authority-tagged conversation plans with the
  static Factorio 2.1.12/Space Age blurb and an explicit no-live-snapshot
  warning. It adds 6 tests; the complete suite has 119 passing tests. All
  authoritative direct routing remains owned by a later Step 6 follow-up.
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
- The complete combined suite has 149 dependency-free tests, including logistics
  schema/provider and trusted rich-name regressions. Routine tests are
  mocked and consume neither Groq quota nor live RCON.
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
- The next read-only architecture increment is a Step 10 parser/compiler
  prototype for a compact Lua-shaped query syntax. The model should reuse its
  Factorio/Lua knowledge instead of receiving an ever-growing proprietary tool
  catalog. Model text is never executed: local code parses a restricted AST,
  permits only allowlisted reads and bounded control flow, and compiles trusted
  queries. Assignments, mutating methods, dynamic evaluation, metaprogramming,
  recursion, unrestricted globals, and unbounded iteration are rejected
  structurally. Existing registered operations remain the live fallback until
  adversarial offline tests and harmless no-public comparisons pass.
- Jimbo is Jimbo the Jr. Engineer. Harmless non-Factorio conversation is in
  scope, and the model may supply the detailed conversational personality.
- Keep the last three completed exchanges separately per player. Do not build a
  dedicated persistent conversation-memory system, but do not deliberately
  suppress persistence that naturally arises from the eventual architecture.
- The model is the primary generic Factorio knowledge source. Broad RCON-backed
  read-only investigation is authoritative for this live game and should answer
  questions that players could otherwise resolve through laborious inspection.
- Management-authorized ghost and blueprint-ghost placement for construction
  bots is an essential first-release feature and the sole world-changing action
  class. Its dedicated validated pipeline may execute Lua/RCON and may narrowly
  accept model-authored Lua/RCON; the general execution prohibition remains.
- Archive all public chat for this single-server project. Long-artifact delivery,
  public cost/quota disclosure, formal latency optimization, explicit additional-
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

- Public replies are the only live model action. Current live-state selection is
  model-planned over validated registered operations; deterministic phrase
  matching is fallback-only. The planned restricted Lua-shaped interface is
  parsed and compiled locally and will never pass model text directly to RCON.
  The model cannot access credentials/files or authorize world-changing actions.
- Unrelated public chat is not sent to Groq. Only explicit leading invocations
  are processed.
- `dlbattle` is the management authority for live chat behavior.
- Routine tests are mocked and must not consume Groq quota or invoke RCON.
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
roadmap, Steps 1-7, the model-directed Step 6 planner, Step 10's minimal
investigation core, Step 11's platform/logistics adapters, quota-safe breadth
changes, and 149 tests. Verify the working tree and latest commit after restart.
Earlier relevant commits are:

- `85bd820 Complete Jimbo chatbot proof of concept`
- `bf3e27b Capture Jimbo full bot design findings`
- `552503f Capture additional Jimbo player findings`

The user-facing `README.md` documents setup, operation, testing, diagnostics,
safety boundaries, and current limitations. The next implementation task is the
recorded Step 10 restricted-query parser/compiler prototype. Begin with
logistics and platform reads already supported by trusted adapters; compare
answers, prompt size, plan validity, RCON volume, execution time, and correction
frequency. Keep existing operations live as fallback and do not publicly enable
compiled model queries before adversarial tests and harmless no-public smokes.

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
