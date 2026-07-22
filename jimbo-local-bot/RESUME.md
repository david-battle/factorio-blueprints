# Jimbo bot cold-start handoff

Read this file first after a new Codex session. Then read
`FULL_BOT_REQUIREMENTS.md`, which is the normative input to the architecture
phase, followed by `FULL_BOT_FINDINGS.md` for the player-testing evidence behind
it. Read `POC_PLAN.md` only when detailed POC history or numbered-step decisions
are needed; it is authoritative but intentionally long.

## Current state (2026-07-22)

- POC Steps 1, 2, 3, 4, 5, 5.5, 5.75, 5.8, and 6 are complete.
- Full Bot Steps 1-7 are complete and deployed. The live bot uses OpenCode Zen
  `big-pickle` as the default model provider, with Groq available as a fallback.
  API key is read from `C:\Users\dlbat\.local\share\opencode\auth.json`.
- Free-form model-authored Lua/RCON is deployed for every player. The model can
  compose arbitrary Factorio commands; local code applies operational framing,
  serialization, attribution, archiving, timeout, and retry with linear backoff
  for transient errors (5xx, 429, network). A post-processor fixes known bad
  Factorio API patterns (e.g. `game.space_platforms` → `game.forces.player.platforms`).
- The complete dependency-free test suite has 171 passing tests.
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
- The live bot uses OpenCode Zen `big-pickle` as the default model provider,
  with Groq `openai/gpt-oss-120b` available as a fallback via `--provider groq`.
  The local Ollama/Qwen path remains implemented but was too weak for
  reliable Factorio answers.
- Step 5.8 requires leading `jimbo` or `hey jimbo`, keeps the last three
  completed exchanges separately per player in memory, and sends structured
  history. Memory is deliberately lost on restart.
- The OpenCode Zen API key is read from `C:\Users\dlbat\.local\share\opencode\auth.json`.
  The Groq key remains at `runtime/groq-api-key.txt` for fallback use.
  The entire runtime directory is ignored. Never print, transcribe, or commit any key.

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
`main`. The full bot is the active implementation with OpenCode Zen big-pickle
as the default provider. Verify the working tree and latest commit after restart.
Earlier relevant commits are:

- `85bd820 Complete Jimbo chatbot proof of concept`
- `bf3e27b Capture Jimbo full bot design findings`
- `552503f Capture additional Jimbo player findings`

The user-facing `README.md` documents setup, operation, testing, diagnostics,
boundaries, and current limitations.

### Latest handoff (2026-07-22)

- The managed full listener is running (query status for current PID).
- The bot now uses OpenCode Zen `big-pickle` (free, OpenAI-compatible API at
  `https://opencode.ai/zen/v1`) as the default model provider.
- Free-form model-authored Lua/RCON is deployed for every player. The model
  composes Factorio commands; local code applies operational framing,
  serialization, archiving, timeout, and retry with linear backoff (1s-5s)
  for transient errors (5xx, 429, network). A post-processor corrects known
  bad Factorio API patterns before execution.
- The complete dependency-free suite passes 171 tests. Automated
  model/provider tests remain mocked and consume no provider quota. Tests may
  invoke live RCON when authoritative Factorio execution is materially useful.

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
10. Live-test and refine the permissive model-authored Lua/RCON path; add safe 429 reset telemetry and retain registered tools only while useful.
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
