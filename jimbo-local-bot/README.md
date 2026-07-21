# Jimbo Factorio Chat Bot

Jimbo is a proof-of-concept chat bot for the local Factorio dedicated server.
It watches newly appended public chat in the server console log, sends explicitly
addressed questions to a language model, and posts a short reply back into the
game through the repository's restricted RCON wrapper.

The currently deployed configuration uses Groq's `openai/gpt-oss-120b`. A local
Ollama client remains available for testing, but the small Qwen models evaluated
during development were not reliable enough for live Factorio questions.

## Player usage

Start a public chat message with `jimbo` or `hey jimbo`:

```text
Jimbo, what ingredients do red circuits need?
Hey Jimbo, and blue?
```

Jimbo responds publicly as:

```text
Jimbo to <player>: <response>
```

The invocation must be at the beginning of the message. A later mention such as
`Start your request with Jimbo` does not activate the bot.

Jimbo remembers at most the last three completed exchanges separately for each
player. It remembers the same compact response shown to the player, limited to
180 characters and shortened at a word boundary when necessary. This memory is
held only in the running process and is lost on restart.
Its prompt also includes a small authoritative server-context block: the server
is running Factorio 2.1.12 with Space Age, Elevated Rails, and Quality enabled.
General recipes and game mechanics are left to the model's existing knowledge;
Jimbo has no search tool or general live-world inspection access.

For each accepted question, Jimbo also runs one fixed read-only server query and
provides the model with the connected player names and current research/progress.
This is the complete POC live-state scope; the model cannot choose or construct
RCON commands.

## Requirements and setup

- Python 3.13 at
  `C:\Users\dlbat\AppData\Local\Programs\Python\Python313\python.exe`.
- The Factorio dedicated-server console log at
  `D:\factorio-server\server-console.log`.
- The repository RCON wrapper and its existing machine-local credential setup.
- For the live Groq provider, a Groq API key stored as the only line in:

  ```text
  jimbo-local-bot/runtime/groq-api-key.txt
  ```

The entire `runtime` directory is ignored by Git. Never commit or print the API
key. See [GROQ_SETUP.md](GROQ_SETUP.md) for the one-time key setup and a
console-only validation procedure.

## Start, stop, test, and inspect

Routine operations use the fixed project launcher. Edit only
`tools/jimbo-action.json`, then run this command exactly as written from the
repository:

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File 'D:\ChatGPT-Factorio-Playground\factorio-blueprints\jimbo-local-bot\tools\jimbo-project.ps1'
```

Supported action-file contents are:

```json
{"action":"status","arguments":[]}
{"action":"start","arguments":["--provider","groq"]}
{"action":"stop","arguments":[]}
{"action":"restart","arguments":["--provider","groq"]}
{"action":"test","arguments":[]}
{"action":"bot","arguments":["--provider","groq"]}
```

`start` runs the listener in the background, `bot` runs it in the foreground,
and `test` runs the dependency-free unit suite. Background process state is
tracked in `runtime/jimbo.pid`.

To perform a manual end-to-end test:

1. Set the action to `status` and confirm the listener is running.
2. In Factorio public chat, send `Jimbo, say hello for a test`.
3. Confirm exactly one `Jimbo to <player>:` reply appears.
4. Inspect the transcript for the accepted request, model response, sanitized
   public message, and confirmed RCON send.

## Runtime diagnostics

Structured events are appended as UTF-8 JSON Lines to:

```text
jimbo-local-bot/runtime/transcript.jsonl
```

Each event is flushed immediately. The transcript records bot lifecycle,
accepted or rejected requests, provider responses, sanitized public messages,
confirmed RCON sends, and errors. It does not intentionally record unrelated
public chat, credentials, or environment variables.

The source Factorio chat log remains:

```text
D:\factorio-server\server-console.log
```

The durable log position is stored in the ignored runtime file:

```text
jimbo-local-bot/runtime/log-cursor.json
```

On its first launch Jimbo starts at the current end of the server log. Later
launches resume at the last complete-line offset, so consumed chat is not
replayed and complete chat written during a short stop can still be processed.
The cursor also detects log truncation and replacement. Do not edit the cursor
while the listener is running; deleting it intentionally resets the next launch
to the current end of the log.

## Safety boundaries

- The model can generate only public reply text.
- Generated text cannot select Lua, PowerShell, an RCON command, or a file.
- Replies are reduced to one line, stripped of Factorio formatting brackets,
  normalized to conservative ASCII for the Windows RCON path, and limited to
  240 characters before insertion into a fixed RCON command.
- Server-authored messages are ignored to prevent reply loops.
- Requests are processed serially with a per-player cooldown, one pending
  request per player, and a bounded queue.
- Jimbo has no world-changing tools and performs no autonomous game actions.
- Live state is limited to one fixed snapshot of online players and current
  research. All other world facts remain unavailable.

## Current limitations

This is a working proof of concept, not a service-grade deployment:

- Conversation memory is lost on restart.
- The cursor provides bounded restart, truncation, and replacement handling but
  is not a general-purpose production log-rotation system.
- There is no Windows service installation, dashboard, moderation system,
  long-term conversation database, or automatic local-model fallback in the
  deployed Groq configuration.
- Model answers can still be incomplete or incorrect and should not be treated
  as authoritative.
- Broader live-state tools and RCON concurrency/locking belong to a future full
  chatbot design, not this proof of concept.

## Full-bot development

The full bot is being built separately from the active POC under
`jimbo_full_bot`. Its architecture and serial roadmap are in
`FULL_BOT_DESIGN.md` and `FULL_BOT_PLAN.md`.

Step 1 provides only a side-effect-free offline shell:

```powershell
& 'C:\Users\dlbat\AppData\Local\Programs\Python\Python313\python.exe' -m jimbo_full_bot --offline
```

The command reports validated redacted configuration. It does not read the API
key, watch live chat, contact Groq, invoke RCON, send messages, or change the
game. The ordinary project `test` action discovers both POC and full-bot tests.

Full Bot Step 2 adds offline storage components only: an append-only tagged
UTF-8 event log with retained 10 MB segments and small versioned flat-text state
files updated through atomic replacement. It adds no JSON storage, SQLite, live
log reader, provider call, or RCON behavior.

Full Bot Step 3 adds the first-pass durable log reader and normalized
chat/join/leave event interface needed by later steps. Step 7 now uses it in the
active full-bot listener with separate full-bot state and archive paths.

Full Bot Step 4 adds first-pass deterministic invocation decisions, self-loop
suppression, durable first/return join classification, and welcome intents. All
welcome templates instruct players to begin queries with `Jimbo`. Delivery is
provided by the minimal Step 5 bridge, and the real hosted model path is
required in Step 7.

Full Bot Step 5 adds the minimal delivery bridge: one-line plain-text rendering,
the fixed RCON wrapper transport, serialized sending, exact archive records,
confirmed-delivery deduplication, and welcome completion. Public delivery is
enabled only by the explicit Step 7 live configuration.
Aggressive content filtering and rich rendering remain a later Step 5 follow-up.

Full Bot Step 6 now has a basic deterministic read-only RCON route. Recognized
questions about connected players, current research/progress, game time, and
available surfaces use one fixed locally authored snapshot and direct trusted
answers. The model never selects or authors RCON. Other requests receive the
static server blurb and continue to ordinary conversation; broader or smarter
state-needs routing remains a later Step 6 follow-up.

Full Bot Step 7 adds the real Groq `openai/gpt-oss-120b` gateway and the live
prototype pipeline. It keeps three successfully delivered exchanges in memory
per player, loses that memory on restart, and never writes or replaces the
existing ignored API key. The managed listener is currently running the full
bot; players can test it by beginning a public chat message with `Jimbo`.

Development history, acceptance results, and the remaining roadmap are in
[POC_PLAN.md](POC_PLAN.md). A concise cold-start handoff is in
[RESUME.md](RESUME.md).
