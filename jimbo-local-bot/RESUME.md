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
  the revision was announced publicly. Broader intelligent state-needs routing
  remains a later Step 6 follow-up.
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
- The complete combined suite has 132 dependency-free tests. Routine tests are
  mocked and consume neither Groq quota nor live RCON.
- The POC is declared proven. Do not add more ambitious POC features; the next
  phase is a separate full-chatbot design.
- Player testing findings through the supplemental 15:18:03 server-time cutoff
  (19:18:03 UTC) are captured in `FULL_BOT_FINDINGS.md`. It contains 45
  representative cases and 27 full-bot design priorities plus the requested
  welcome/welcome-back behavior.
- `FULL_BOT_REQUIREMENTS.md` is complete enough to begin architecture design. It
  contains stable requirement IDs, 25 initial acceptance scenarios, and a
  resolved product-decision register.
- The full-chatbot architecture draft is in `FULL_BOT_DESIGN.md`, and the
  fourteen-step serial implementation roadmap is in `FULL_BOT_PLAN.md`. Do not
  turn individual findings into more POC prompt patches.
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
  deterministic local phrase matching. The planned Step 6 follow-up lets the
  model propose allowlisted read-only operations, but it still cannot author
  Lua/RCON, access credentials/files, or authorize world-changing operations.
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
`main`. This handoff is being committed with the full-bot architecture, plan,
Steps 1-7 implementation, basic Step 6 live-state follow-up, and tests. Verify
the working tree and latest commit after restart. Earlier relevant commits are:

- `85bd820 Complete Jimbo chatbot proof of concept`
- `bf3e27b Capture Jimbo full bot design findings`
- `552503f Capture additional Jimbo player findings`

The user-facing `README.md` documents setup, operation, testing, diagnostics,
safety boundaries, and current limitations. The next implementation task is the
recorded Step 6 model-directed state-needs planner in `FULL_BOT_PLAN.md`:
one strict planning pass chooses zero or more locally allowlisted read-only
tools, local code validates and executes fixed RCON, and one answer pass receives
trusted results with provenance. Keep the deterministic matcher temporarily as
a rollout fallback. Live testing specifically showed that provenance follow-ups
currently repeat the player list or let the model contradict the fresh result;
the planner/synthesis path must fix that without permitting model-authored RCON.

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
