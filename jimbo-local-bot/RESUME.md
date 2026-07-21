# Jimbo bot cold-start handoff

Read this file first after a new Codex session, then read `POC_PLAN.md` for the
full numbered roadmap and recorded decisions.

## Current state (2026-07-21)

- Steps 1, 2, 3, 4, 5, 5.5, 5.75, and 5.8 are complete.
- Step 6 is intentionally not started. It is the next numbered step if the user
  chooses to resume implementation.
- The live bot uses Groq `openai/gpt-oss-120b`, with no automatic Ollama
  fallback. The local Ollama/Qwen path remains implemented but was too weak for
  reliable Factorio answers.
- Step 5.8 requires leading `jimbo` or `hey jimbo`, keeps the last three
  completed exchanges separately per player in memory, and sends structured
  history. Memory is deliberately lost on restart.
- The Step 5.8 suite has 34 dependency-free tests. Its console-only hosted smoke
  test correctly resolved `And blue?` from a prior red-circuit exchange.
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
file was left on `status`; always query status rather than trusting a recorded
PID. Listener stdout/stderr and the structured transcript are under `runtime/`.

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

## Working tree and next action

The Jimbo implementation and documentation have not yet been committed in this
work sequence. Inspect `git status` and preserve unrelated user changes. The
most logical next implementation task is Step 6 (durable restart/cursor
behavior), but do not begin it unless requested. A README remains listed among
the initial deliverables and can be added during Step 6 or final POC cleanup.
