# Jimbo bot cold-start handoff

Read this file first after a new Codex session. Then read
`FULL_BOT_FINDINGS.md`, which is the primary input to the next design phase.
Read `POC_PLAN.md` only when detailed POC history or numbered-step decisions are
needed; it is authoritative but intentionally long.

## Current state (2026-07-21)

- Steps 1, 2, 3, 4, 5, 5.5, 5.75, 5.8, and 6 are complete.
- Minimal Step 5.9 is complete: each accepted question receives connected-player
  and current-research data from one fixed read-only RCON query.
- The POC is declared proven. Do not add more ambitious POC features; the next
  phase is a separate full-chatbot design.
- Player testing findings through 14:38:47 server time (18:38:47 UTC) are
  captured in `FULL_BOT_FINDINGS.md`. It contains 42 representative cases and
  25 full-bot design priorities plus the requested welcome/welcome-back behavior.
- The intended next deliverable is a full-chatbot design document derived from
  those findings. Do not turn individual findings into more POC prompt patches.
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

The implementation and latest findings are committed on `main`. At this handoff,
`main` matches `origin/main`; verify that again rather than assuming it remains
true. Relevant commits are:

- `85bd820 Complete Jimbo chatbot proof of concept`
- `bf3e27b Capture Jimbo full bot design findings`
- `552503f Capture additional Jimbo player findings`

The user-facing `README.md` documents setup, operation, testing, diagnostics,
safety boundaries, and current limitations. Step 6 durable cursor behavior is
implemented in `runtime/log-cursor.json`, and minimal Step 5.9 is one fixed
read-only snapshot. The next task, when requested, is to design the full chatbot
from `FULL_BOT_FINDINGS.md`, preserving a clear boundary between the proven POC
and the new architecture.

## Fresh-session checklist

1. Read this file and `FULL_BOT_FINDINGS.md`.
2. Run `git status` and preserve any user changes.
3. If touching the live bot, query listener status through the fixed project
   launcher before assuming its state.
4. Do not clear runtime files or the Factorio server console log.
5. Treat chat after the recorded findings cutoff as uncaptured evidence unless
   the user explicitly requests another review.
6. Begin the full-bot design as a separate document/project phase; do not reopen
   the POC merely because the desired full bot needs more capabilities.
