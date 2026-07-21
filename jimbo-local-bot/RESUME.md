# Jimbo bot cold-start handoff

Read this file first after a new Codex session. Then read
`FULL_BOT_REQUIREMENTS.md`, which is the normative input to the architecture
phase, followed by `FULL_BOT_FINDINGS.md` for the player-testing evidence behind
it. Read `POC_PLAN.md` only when detailed POC history or numbered-step decisions
are needed; it is authoritative but intentionally long.

## Current state (2026-07-21)

- Steps 1, 2, 3, 4, 5, 5.5, 5.75, 5.8, and 6 are complete.
- Minimal Step 5.9 is complete: each accepted question receives connected-player
  and current-research data from one fixed read-only RCON query.
- The POC is declared proven. Do not add more ambitious POC features; the next
  phase is a separate full-chatbot design.
- Player testing findings through the supplemental 15:18:03 server-time cutoff
  (19:18:03 UTC) are captured in `FULL_BOT_FINDINGS.md`. It contains 45
  representative cases and 27 full-bot design priorities plus the requested
  welcome/welcome-back behavior.
- `FULL_BOT_REQUIREMENTS.md` is complete enough to begin architecture design. It
  contains stable requirement IDs, 25 initial acceptance scenarios, and a
  resolved product-decision register.
- The intended next deliverable is a separate full-chatbot architecture/design
  document derived from the requirements. Do not turn individual findings into
  more POC prompt patches.
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
- The complete suite has 44 dependency-free tests. Hosted smoke tests resolved
  contextual circuit questions and live server state; minimal Step 5.9 also
  passed a real public player request.
- The Groq key is machine-local at `runtime/groq-api-key.txt`. The entire
  runtime directory is ignored. Never print, transcribe, or commit the key.

## Listener operations

Change only `tools/jimbo-action.json`, then run the exact fixed launcher from
the repository `AGENTS.md`. Supported actions are:

- `{"action":"status","arguments":[]}`
- `{"action":"start","arguments":["--provider","groq"]}`
- `{"action":"stop","arguments":[]}`
- `{"action":"restart","arguments":["--provider","groq"]}`
- `{"action":"test","arguments":[]}`
- `{"action":"bot","arguments":["--provider","groq"]}` for a foreground run

`start`, `stop`, and `restart` use `runtime/jimbo.pid`, avoiding approval for
changing process IDs. At this handoff, the listener was running and the action
file was left on `status`. A live status check reported PID 9288, but always
query status rather than trusting this recorded PID. Listener stdout/stderr and
the structured transcript are under `runtime/`.

## Important behavior and boundaries

- Public replies are the only live model action. The model cannot choose Lua,
  RCON commands, files, or world-changing operations.
- Unrelated public chat is not sent to Groq. Only explicit leading invocations
  are processed.
- `dlbattle` is the management authority for live chat behavior.
- Routine tests are mocked and must not consume Groq quota or invoke RCON.
- A repeated CLI `--prompt` sequence exists for console-only contextual smoke
  tests. Do not add `--send-to` when using multiple prompts.
- The structured live transcript is `runtime/transcript.jsonl`. Factorio's raw
  chat remains in `D:\factorio-server\server-console.log`.
- Never reset, truncate, or discard either log. Players are continuing to use
  the POC and later conversations may be useful full-bot design evidence.
- The POC transcript is append-only but intentionally records bot workflow, not
  every unrelated chat line or join/leave event. Until the full bot implements
  the canonical archive requirement in `FULL_BOT_FINDINGS.md`, use the server
  console log when complete conversational context is required.
- The findings cutoff is not a log-retention boundary. Chat after the cutoff
  remains available for a later review; do not scrape or summarize it unless
  the user asks.

## Working tree and next action

The implementation, findings, requirements baseline, and this handoff are
committed on `main`. The requirements/handoff commit is intentionally left for
the user to push, so expect local `main` to be ahead of `origin/main` by one
commit at the start of the next context. Verify rather than assuming. Earlier
relevant commits are:

- `85bd820 Complete Jimbo chatbot proof of concept`
- `bf3e27b Capture Jimbo full bot design findings`
- `552503f Capture additional Jimbo player findings`

The user-facing `README.md` documents setup, operation, testing, diagnostics,
safety boundaries, and current limitations. Step 6 durable cursor behavior is
implemented in `runtime/log-cursor.json`, and minimal Step 5.9 is one fixed
read-only snapshot. The next task is to create the full chatbot architecture and
design document from `FULL_BOT_REQUIREMENTS.md`, using the findings as evidence
and preserving a clear boundary between the proven POC and the new architecture.

## Fresh-session checklist

1. Read this file, `FULL_BOT_REQUIREMENTS.md`, and `FULL_BOT_FINDINGS.md`.
2. Run `git status` and preserve any user changes.
3. If touching the live bot, query listener status through the fixed project
   launcher before assuming its state.
4. Do not clear runtime files or the Factorio server console log.
5. Treat chat after the latest recorded findings cutoff as uncaptured evidence unless
   the user explicitly requests another review.
6. Begin the full-bot architecture/design as a separate document/project phase;
   do not reopen the POC merely because the desired full bot needs more
   capabilities.
