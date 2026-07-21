# Jimbo bot cold-start handoff

Read this file first after a new Codex session, then read `POC_PLAN.md` for the
full numbered roadmap and recorded decisions.

## Current state (2026-07-21)

- Steps 1, 2, 3, 4, 5, 5.5, 5.75, 5.8, and 6 are complete.
- Minimal Step 5.9 is complete: each accepted question receives connected-player
  and current-research data from one fixed read-only RCON query.
- The POC is declared proven. Do not add more ambitious POC features; the next
  phase is a separate full-chatbot design.
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

The implementation is committed on `main`. Inspect `git status` and preserve
unrelated user changes before future work. The user-facing `README.md` documents
setup, operation, testing, diagnostics, safety boundaries, and current
limitations. Step 6 durable cursor behavior is implemented in
`runtime/log-cursor.json`, and minimal Step 5.9 is implemented as one fixed
read-only snapshot. The next task, when requested, is to design the full chatbot
rather than extend this POC.
