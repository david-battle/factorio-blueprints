# Proof-of-Concept Plan

## Objective

Prove the complete chat loop with the smallest observable implementation. The
POC began with local inference and now uses a free hosted model because live
testing showed that the lightweight local models were not useful enough:

```text
new Factorio chat line beginning with "jimbo" or "hey jimbo"
    -> parse player and request
    -> generate a short response with Groq GPT-OSS 120B
    -> send the response to Factorio through RCON
    -> continue watching without responding to itself
```

The proof of concept runs as a project-managed background process for live use,
with foreground execution retained for diagnostics. It is not installed as a
service and does not expose world-changing game tools.

## Implementation approach

The priority is to establish a working end-to-end chat loop quickly, then learn
from the live result. Implementation details that are not required for that loop
should be decided only when the work reaches them and recorded in this plan as
they are settled.

If a planned feature or robustness measure cannot be made to work quickly:

1. time-box the investigation;
2. replace it with a simpler approach if one is obvious;
3. otherwise omit or defer it;
4. keep moving toward the smallest usable bot.

Do not delay the proof of concept for comprehensive locking, rotation handling,
persistent memory, retries, elaborate configuration, perfect resource
measurement, or other production concerns. A visible limitation documented in
the README is preferable to speculative complexity. The only exceptions are
basic safeguards needed to prevent an obvious response loop, command injection,
or accidental arbitrary RCON execution.

Update this document as implementation decisions are made. Decisions should be
based on observed behavior of the local Ollama installation, Factorio log, and
RCON wrapper rather than designing every edge case in advance.

## Step convention

The implementation is divided into six numbered top-level steps plus inserted
steps 5.5, 5.75, and 5.8 below. A request such as `implement step 1`, `implement
step 5.5`, or `implement step 5.8` refers to the complete matching section,
including its acceptance check. The numbered activities inside a step describe
that step's work and are not separate project-level step identifiers.

Complete and verify each requested step before moving to the next unless a
later step is explicitly requested at the same time. Record material decisions,
simplifications, and deferred items in this plan as the implementation evolves.

## Step 1: Verify local inference

1. Check whether Ollama is installed and whether its local API is reachable.
2. Pull a 4-bit Qwen3 1.7B model if it is not already available.
3. Send one short test prompt with thinking disabled.
4. Record basic observations:
   - model load time;
   - response latency;
   - approximate CPU, RAM, and GPU impact while generating;
   - whether Factorio and the dedicated server remain responsive.
5. Use a short context and output limit representative of in-game chat.

Acceptance check: Qwen3 1.7B returns a coherent short answer locally without
unacceptable impact on the game or server.

### Step 1 result (2026-07-21)

Status: complete; acceptance check passed.

- Ollama was already running locally at `http://127.0.0.1:11434`, version
  `0.30.6`, although its executable was not available on the shell `PATH`.
- Pulled `qwen3:1.7b` successfully through the local Ollama API. Ollama reports
  a 1.27 GB `Q4_K_M` artifact and identifies its parameter size as 2.0B.
- Used `/api/chat` with `think: false`, `num_ctx: 2048`, `num_predict: 80`, and
  `temperature: 0.7`. Both trials returned short responses with no thinking
  content.
- Cold trial: 3.82 seconds wall time, including 3.38 seconds reported model
  load time, with 13 output tokens at approximately 98 tokens/second.
- Warm trial: 1.84 seconds wall time, including 1.31 seconds reported load
  handling, with 22 output tokens at approximately 64 tokens/second.
- Available system memory changed from about 20.05 GB before the cold request
  to 19.38 GB afterward. The loaded `llama-server` process showed about 0.63 GB
  working set. These are lightweight observations, not controlled benchmarks.
- The NVIDIA RTX 2080 Super Max-Q reported 6.5 GB of 8 GB VRAM in use while the
  game, server, model, and other applications were active; no isolated model
  VRAM baseline was taken.
- A read-only `/players` RCON query returned immediately after inference, which
  confirmed that the dedicated server remained responsive.
- Response quality was coherent but generic. Prompt and persona quality remain
  Step 3 concerns and do not block the runtime proof.

Decision: keep Qwen3 1.7B as the proof-of-concept model and use Ollama's local
HTTP API directly rather than depending on the `ollama` CLI being on `PATH`.
Treat this model choice as provisional: finish the live end-to-end proof with
1.7B, then consider a somewhat larger model if live response quality is not good
enough. Keep the model name configurable so that evaluation does not require an
architecture or code-path change.

## Step 2: Prove log tailing and parsing

1. Create a small Python foreground program in this project directory.
2. On first start, begin at the current end of
   `D:\factorio-server\server-console.log` so historical chat is not replayed.
3. Watch appended records and parse public `[CHAT]` lines into a player name and
   message.
4. Match `jimbo` as a complete word, case-insensitively.
5. Strip the attention word and nearby conversational punctuation from the
   request.
6. Print matched player/request pairs to the local console without calling the
   model or RCON yet.
7. Ignore join/leave events, server diagnostics, malformed lines, and chat that
   does not contain the trigger.

Acceptance check: a newly typed message such as `Jimbo who is online?` produces
exactly one correctly parsed local event, while `jimbob` and ordinary chat
produce none.

### Step 2 result (2026-07-21)

Status: complete; acceptance behavior passed in an isolated cross-process log
simulation, and startup against the real server log passed.

- Added the dependency-free Python 3.13 foreground watcher in `jimbo_bot.py`.
- The watcher opens the configured log in binary read mode, starts at its
  current end, polls for appended bytes, waits for complete lines, and decodes
  UTF-8 with replacement for malformed bytes.
- Public `[CHAT]` records are parsed into timestamp, player, and message fields.
  Other records and malformed lines are ignored.
- `jimbo` is matched case-insensitively as a complete word. Nearby
  conversational punctuation is removed from the request, while `jimbob` does
  not match.
- Six unit tests cover public-chat parsing, ignored records, case-insensitive
  whole-word matching, `jimbob`, an empty request, start-at-end behavior, and a
  partial appended line.
- A cross-process simulated writer appended ordinary chat, `jimbob`, and one
  valid Jimbo request. The foreground watcher emitted exactly the valid new
  request and did not replay the historical Jimbo line.
- A brief smoke test opened
  `D:\factorio-server\server-console.log`, printed its watching status, emitted
  no historical messages, and exited without an error after being stopped.

Decision: retain Python for the implementation. Python 3.13 is installed at
`C:\Users\dlbat\AppData\Local\Programs\Python\Python313\python.exe`; restricted
tool sessions may require explicit host permission to execute that user-profile
path even though the interpreter is installed and functional.

Developer workflow decision: use the fixed project launcher at
`tools\jimbo-project.ps1` for routine execution. The fixed launcher reads
`tools\jimbo-action.json`, validates a narrow project action, and passes bot
arguments only to `jimbo_bot.py`. It supports `test`, foreground `bot`, and
PID-tracked `start`, `stop`, `restart`, and `status` listener operations. This
keeps listener lifecycle operations behind the same one-time-approved command
instead of requiring approval for each changing process ID, and keeps the out-of-workspace
Python path in one place and permits one byte-for-byte approved project command.
Continue changing the Python source, tests, and action file normally; do not
modify the approved launcher merely to run unrelated commands.

## Step 3: Connect the local model

1. Call Ollama's local HTTP API for each matched request.
2. Use Qwen3 1.7B with thinking disabled.
3. Give the model a short system prompt describing Jimbo as a concise, friendly
   Factorio server chat bot.
4. Limit the context to 2,048 to 4,096 tokens and the response to approximately
   80 tokens.
5. Initially retain no history or only a very small in-memory history per
   player; persistence is not required for the proof of concept.
6. Serialize generation so only one model request runs at a time.
7. Print the proposed reply locally before enabling RCON output.

Acceptance check: a triggered chat request produces one short, relevant local
response with no visible thinking block.

### Step 3 result (2026-07-21)

Status: complete; acceptance check passed.

- Added a dependency-free Ollama client using Python's standard-library
  `urllib.request` and `json` modules.
- Requests use `qwen3:1.7b`, `/api/chat`, `stream: false`, `think: false`, a
  2,048-token context, an 80-token output limit, temperature 0.7, a 60-second
  timeout, and a two-minute model keep-alive.
- The foreground watcher now sends each matched request to Ollama synchronously
  and prints `Jimbo -> <player>: <response>` locally. It still sends nothing to
  Factorio or RCON.
- Empty requests receive a small fallback greeting prompt. Connection failures,
  invalid JSON, and missing response content become visible `OllamaError`
  messages without terminating the watch loop.
- Added `--prompt` for a one-shot local model check that does not require a log
  event.
- Three mocked Ollama tests verify the non-thinking bounded payload, timeout,
  empty-request fallback, returned content, and rejection of missing content.
  The complete suite now has nine passing tests.
- The first real prompt returned a short but irrelevant recommendation to build
  another smelter after being told plate automation already existed. The system
  prompt was tightened to respect player-stated facts and include minimal
  early-game Factorio grounding.
- Repeating the real prompt then returned: `Build a green circuit to get started
  with science.` This is short, relevant, and contained no visible thinking
  block.

Decision: keep the initial bot synchronous and console-only. More sophisticated
prompting, memory, and concurrency remain deferred until the live chat loop
demonstrates a need for them.

### Model comparison note (2026-07-21)

The first live 1.7B test hallucinated a circuit board, green circuit module,
workshop, market, and tools when asked how to make green circuits. Qwen3 4B
`Q4_K_M` was downloaded and evaluated with the same question before changing
the live bot.

- Qwen3 1.7B answered at roughly 99 to 101 output tokens/second but repeatedly
  invented a green circuit board and green circuit generator.
- Qwen3 4B answered at roughly 53 to 55 output tokens/second. With thinking
  disabled it emitted internal planning as visible content and reached the
  output cap without an answer. Explicit `/no_think` did not correct this.
- With thinking enabled, Ollama separated the reasoning, but the 4B model used
  the full 400-token test budget hallucinating circuit assemblers and circuit
  wires and produced no final answer.
- The 4B artifact is 2.33 GB versus 1.27 GB for 1.7B. Keeping both model runners
  resident pushed observed GPU memory to about 7.6 of 8 GB; unloading 4B reduced
  it to about 4.7 GB.

Decision: do not switch the live bot to Qwen3 4B. Keep 1.7B temporarily while a
different model family or a small authoritative Factorio knowledge layer is
evaluated. Model size alone did not solve factual reliability.

## Step 4: Connect Factorio replies

1. Send the generated response through the repository's existing fixed RCON
   wrapper and credential flow.
2. Reply publicly and clearly identify the bot, for example:
   `Jimbo: <response>`.
3. Sanitize line breaks and enforce a conservative maximum message length
   before constructing the RCON payload.
4. Never interpret generated text as Lua, PowerShell, or an RCON command.
5. Log the RCON result and surface failures in the foreground console.

Implementation defaults agreed before starting this step:

- Format public replies as `Jimbo to <player>: <response>` so busy chat makes
  the intended recipient clear.
- Test sanitization and inspect the completed command locally before the first
  live send.
- Reuse the repository's fixed RCON credential flow; never copy the password
  into this project.
- Keep the reply path narrowly scoped to public text. Do not allow the model to
  select an RCON command, Lua expression, executable, or destination file.
- If a robust encoding technique becomes time-consuming, reduce the permitted
  response character set or omit problematic formatting instead of building a
  general command interpreter.

Acceptance check: a player can address Jimbo in public chat and receive one
public model-generated response in Factorio.

### Step 4 result (2026-07-21)

Status: complete; the model-to-public-RCON path was confirmed live, and the
log-trigger path remains covered by the Step 2 follower tests and simulation.

- Added plain-text response sanitization that removes control characters,
  collapses whitespace, removes Factorio square-bracket formatting delimiters,
  sanitizes the addressed player name, and limits the complete public message
  to 240 characters.
- Public responses use `Jimbo to <player>: <response>`.
- The only generated RCON shape is a fixed
  `/silent-command game.print([[<sanitized message>]]);rcon.print(...)` payload.
  Because square brackets are removed from dynamic text, model output cannot
  close the Lua long string. The model never selects Lua or an RCON command.
- The bot writes the complete command to the repository's existing
  `tools/rcon-command.txt`, invokes the existing password-handling wrapper, and
  requires the `JIMBO_REPLY_SENT` RCON marker before reporting success.
- The prior command-file contents are restored byte-for-byte after every send,
  including after an invocation error. Byte preservation avoids meaningless Git
  changes from Windows newline normalization.
- The watcher now synchronously sends a confirmed public reply after printing
  the local model response. Server-authored chat is ignored as an immediate
  defense against a response loop; Step 5 will formalize loop and spam behavior.
- Added five RCON/reply tests covering sanitization, formatting and length,
  exact fixed command construction, wrapper use and byte-for-byte restoration,
  and missing-confirmation failure. The complete suite now has 14 passing tests.
- The one-shot live model prompt produced `The local Jimbo bot Step 4 public
  reply test worked.` RCON then confirmed the public message `Jimbo to dlbattle:
  The local Jimbo bot Step 4 public reply test worked.`

Decision: keep the fixed, sanitized Lua long-string reply rather than adding a
general escaping layer. Keep command-file locking deferred unless concurrent
RCON use causes a real conflict.

## Step 5: Prevent loops and trivial spam

1. Explicitly identify and ignore messages emitted by the server/RCON bot.
2. Add one active or queued request per player.
3. Add a short, configurable per-player cooldown.
4. Bound the global request queue.
5. Confirm that the bot's own reply cannot trigger another response even if it
   contains the word `Jimbo`.

Acceptance check: one player message produces one reply, bot output produces no
reply, and rapid duplicate messages cannot create an unbounded queue.

### Step 5 result (2026-07-21)

Status: complete; acceptance behavior is covered by the request-gate,
self-message, and existing end-to-end component tests.

- Added a `RequestGate` with a default five-second per-player cooldown, maximum
  queue length of five, and at most one pending request per player. Player keys
  are case-insensitive.
- The watcher reads each newly available log batch, offers valid requests to the
  bounded gate, reports ignored requests locally, and processes accepted work
  synchronously in arrival order.
- A player remains pending through model generation and the RCON send. The
  cooldown begins when processing finishes, whether the request succeeded or
  failed, so rapid accumulated duplicates are rejected when the watcher next
  reads the log.
- Only one model request can run at a time. Chat written while the model is busy
  remains in Factorio's existing log rather than creating an unbounded in-memory
  bot queue.
- `[CHAT]` records authored by `server` or `<server>` are explicitly rejected
  before trigger extraction, preventing a public `Jimbo to ...` reply from
  triggering the bot if server output is ever represented as public chat.
- Added configurable `--cooldown` and `--max-queue` arguments with validated
  non-negative and positive bounds respectively.
- Four new tests verify server-message rejection, one pending request per player,
  cooldown expiration, and the global queue bound. The complete suite now has
  18 passing tests.

Decision: retain the simple synchronous gate. Do not add threads, asynchronous
workers, persistent rate-limit state, accounts, or moderation machinery unless
live usage demonstrates a concrete need.

If cooldown or queue management starts delaying the proof of concept, use the
simplest synchronous behavior: process one request at a time and ignore new
triggered messages while busy. More polished queuing can be added later.

## Step 5.5: Add a local transcript log

The first live chat test showed that public replies sent with `game.print` do
not appear in `server-console.log`, while the approved long-running launcher may
not surface its child process output to Codex. Add a small durable transcript so
live behavior can be inspected without relying on either channel.

1. Write a UTF-8, line-oriented transcript under a project-local runtime
   directory that is excluded from Git.
2. Record timestamps and structured event types for:
   - accepted player requests;
   - ignored requests and their reason;
   - generated model responses;
   - sanitized public messages;
   - confirmed RCON sends;
   - Ollama and RCON errors;
   - bot startup and clean or interrupted shutdown.
3. Flush every event immediately so the transcript remains useful while the bot
   is still running or after it is forcibly stopped.
4. Keep ordinary console output for interactive use, but do not depend on it as
   the only diagnostic record.
5. Avoid storing the RCON password, complete environment variables, arbitrary
   command lines, or unrelated server chat in the transcript.
6. Add a configurable transcript path with a sensible default under
   `jimbo-local-bot/runtime/`.
7. Add tests for event formatting, UTF-8 text, immediate flush behavior, and
   omission of unrelated public chat.

Acceptance check: after a live player request, the transcript can be read while
the bot is still running and shows the request, generated response, sanitized
public message, and confirmed RCON result (or a clear error), without exposing
credentials or recording unrelated chat.

If structured JSON Lines slows implementation, use a clearly delimited plain
text format instead. Do not add log rotation, a database, dashboard, or remote
logging during this step.

### Step 5.5 implementation result (2026-07-21)

Status: complete; the startup/read-while-running and complete live
request-to-RCON acceptance checks passed.

- Added an append-only UTF-8 JSON Lines transcript with an ISO 8601 UTC
  timestamp and explicit event type on every record.
- Each event opens the transcript in append mode, writes one complete line,
  flushes it, and closes the handle. Events are therefore readable immediately
  and do not depend on buffered launcher output.
- The default path is `jimbo-local-bot/runtime/transcript.jsonl`; the entire
  runtime directory is excluded from Git. `--transcript` can select another
  local path.
- Instrumented startup, accepted and ignored requests, model responses,
  sanitized public messages, confirmed RCON sends, Ollama/RCON errors, and clean
  or keyboard-interrupted shutdown.
- Only explicitly handled bot events are recorded. Unrelated chat, credentials,
  environment variables, and the RCON password are not read into the
  transcript.
- Added two transcript tests for immediately readable UTF-8 JSON Lines and
  omission of unrelated/password text. The complete suite now has 20 passing
  tests.
- Replaced the pre-transcript live bot with the instrumented build. Its startup
  event was read successfully from the transcript while the new process was
  still running.
- Live acceptance request: `dlbattle` sent `Jimbo test`, which was recorded as
  the cleaned request `test`. Qwen3 generated `Testing the server... Let's see
  if everything is working properly.` The transcript then recorded the
  sanitized public message and its confirmed RCON send. All four events were
  readable while the bot remained active.

## Step 5.75: Evaluate a free hosted model provider

Local Qwen3 1.7B and 4B both failed basic Factorio factual questions, while
running multiple local models also competed with the game for GPU memory. Add a
hosted provider without removing the working local path.

1. Keep model generation behind a provider-neutral client interface.
2. Add Groq Chat Completions support using `openai/gpt-oss-120b` and Python's
   standard library.
3. Read the API key from the ignored local runtime file
   `runtime/groq-api-key.txt`; never accept it as a committed configuration
   value or write it to the transcript.
4. Use the current official endpoint and parameters:
   `POST /openai/v1/chat/completions`, `max_completion_tokens`, and
   `include_reasoning: false`.
5. Preserve Ollama as an optional fallback and identify the provider/model that
   actually answered in each transcript response event.
6. Handle missing credentials, timeouts, invalid responses, HTTP failures, and
   rate limits with clear errors.
7. Test all behavior with mocked HTTPS calls before requesting a real key.
8. Make the first real request console-only using the green-circuit question.
   Do not switch or restart public chat until that answer has been inspected.

Acceptance check: with one locally stored Groq API key, the one-shot console
test returns a short, factually useful green-circuit answer from GPT-OSS 120B,
the transcript identifies Groq and the model, the key appears in no output or
tracked file, and no message is sent to Factorio.

### Step 5.75 implementation result (2026-07-21)

Status: complete; mocked verification, credential hygiene, and the console-only
GPT-OSS 120B acceptance check passed.

- Added `ModelClient`, common `ModelError`, Groq, Ollama, and fallback clients.
- Added `--provider`, `--fallback-provider`, Groq URL/key-file settings, and a
  provider-specific `--model` override while retaining Ollama as the default.
- Groq requests use an authorization header, a 256-token completion cap that
  includes low-effort hidden reasoning, excluded reasoning content, temperature
  0.3, and the existing 60-second timeout.
- Transcript startup and response events now record the configured or actual
  provider and model without recording credentials.
- Added seven Groq/fallback tests covering authenticated payload shape, key-file
  loading, a missing key, rate-limit retry information, network timeout,
  primary selection, and Ollama fallback. The complete suite has 27 passing
  tests.
- Added `GROQ_SETUP.md` with the exact one-time secret-file handoff and first
  console-only validation procedure.
- The first HTTPS requests reached Cloudflare but were rejected with error 1010
  because Python's default browser signature was blocked. Adding explicit
  `Accept` and normal Groq API-client `User-Agent` headers resolved the edge
  rejection; the key itself was valid and did not need to be recreated.
- An 80-token completion cap was too small because GPT-OSS consumed it with
  hidden reasoning. The Groq configuration now uses low reasoning effort,
  excludes reasoning content, and allows 256 total completion tokens while the
  existing public-message sanitizer retains the 240-character game limit.
- The first ungrounded 120B answer was fluent but confused the community term
  `green circuit` with a separate item. A compact terminology rule identifying
  green circuits as electronic circuits and limiting recipe answers to direct
  ingredients corrected the behavior without embedding the recipe itself.
- Final console-only acceptance answer: `Electronic circuit (green circuit):
  1 iron plate + 3 copper cable.` No RCON message was sent during evaluation.
- Windows console output is explicitly configured for UTF-8 after the first
  hosted answer exposed a `cp1252` printing failure on narrow Unicode spaces.
- The full suite now has 28 passing tests.

Decision: use Groq GPT-OSS 120B as the live primary provider with no automatic
Ollama fallback initially. A clear logged failure is preferable to silently
falling back to the known-unreliable local model.

Live deployment: the prior Ollama watcher was stopped and replaced with a Groq
watcher. Its transcript startup event identifies provider `groq` and model
`openai/gpt-oss-120b`; the ignored key remained absent from Git and output.

## Step 5.8: Tighten invocation and add bounded conversation context

The first hosted-model conversation showed that matching `jimbo` anywhere in a
message causes false activations, while stateless requests cannot resolve short
follow-ups such as `and blue?`. Improve conversational continuity without
turning Jimbo into an autonomous participant or filling the prompt with a large
Factorio knowledge base.

1. Trigger only when a public message begins with the complete word `jimbo`,
   case-insensitively, after optional leading whitespace and punctuation.
2. Also accept the natural leading form `hey jimbo`. Do not trigger on later
   mentions, explanations, quotations, or third-person discussion of Jimbo.
3. Retain at most the last three completed player/Jimbo exchanges separately for
   each player.
4. Send history as structured user and assistant chat messages before the new
   request rather than concatenating it into one unstructured prompt.
5. Keep history in memory only. Do not add persistence or restore it after a bot
   restart during this step.
6. Add an exchange to history only after a valid model response. Do not teach
   the history from ignored requests, provider errors, or failed/empty model
   responses.
7. Keep the system prompt compact. A short terminology alias hint may identify
   green/electronic, red/advanced, and blue/processing circuits, but do not
   embed or maintain a recipe catalog in the prompt.
8. Continue requiring explicit invocation. Do not send all unrelated public
   chat to Groq and do not ask the model to decide autonomously when to chime in.
9. Add dependency-free mocked regression tests for:
   - leading `jimbo` and `hey jimbo` activation;
   - no activation for a later mention of Jimbo;
   - follow-up history ordering;
   - three-exchange truncation;
   - per-player isolation;
   - exclusion of ignored and failed requests.
10. Mocked regression tests must not call Groq, Ollama, RCON, or consume hosted
    quota. After they pass, run at most one optional console-only hosted smoke
    conversation before restarting the live watcher.

Acceptance check: an announcement such as `Start your request with jimbo and he
will respond` does not trigger; `Jimbo, what about red circuits?` followed by
`Jimbo, and blue?` sends the prior exchange as bounded context and produces a
blue-circuit/processing-unit answer; another player's history is not included;
and all routine regression tests run without network or RCON access.

### Step 5.8 implementation result (2026-07-21)

Status: complete; the mocked suite and hosted contextual acceptance check passed.

- Activation now requires leading `jimbo` or `hey jimbo`, allowing surrounding
  punctuation but rejecting later mentions and longer words such as `jimbob`.
- The watcher retains three completed exchanges per player in memory and sends
  them as ordered user/assistant messages. Player histories remain isolated and
  failed generations are not remembered.
- Both Groq and Ollama accept the same structured history. The compact prompt
  contains terminology aliases for green, red, and blue circuits but no recipe
  catalog.
- All 34 dependency-free regression tests passed without network or RCON calls.
- One console-only Groq smoke conversation answered the red-circuit recipe and
  then resolved `And blue?` to a processing unit with the correct direct recipe.
  Neither response was sent to Factorio.

Explicitly deferred:

- persistent conversation memory;
- whole-server conversational context;
- autonomous decisions to interject;
- a prompt-sized recipe or prototype encyclopedia;
- retrieval or deterministic recipe tools.

## Step 6: Restart behavior

Status: not started. The user explicitly held this step for later. The project
launcher now provides PID-tracked listener lifecycle commands, but durable chat
cursor/replay behavior remains unimplemented and is the next numbered step.

1. Persist a minimal log cursor or equivalent file identity and offset.
2. Resume safely after a normal restart without replaying already handled chat.
3. Detect log truncation or rotation and resume from a safe position.
4. Keep configuration such as paths, model name, limits, and cooldown outside
   the main program logic.

Acceptance check: stopping and restarting the foreground bot does not repeat an
old response, and new chat continues to work.

This phase is optional for the first live demonstration. If reliable cursor or
rotation handling is not quick to implement, start at the end of the current log
on every launch and document that behavior instead.

## Initial deliverables

- A Python foreground bot program.
- A small configuration file or documented environment settings.
- Automated tests for chat parsing, whole-word triggering, message cleanup,
  self-message rejection, and length sanitization.
- A short README with installation, model setup, startup, shutdown, and manual
  end-to-end test instructions.
- A local runtime log and cursor location excluded from Git.

## Explicitly deferred

The proof of concept will not initially include:

- installation as a Windows service;
- a Factorio mod;
- arbitrary Lua or RCON generation by the model;
- world-changing game actions;
- long-term conversation databases;
- general web access beyond the implemented Groq model API;
- elaborate permissions, accounts, dashboards, or moderation systems.
- production-grade file locking, retry policies, and log rotation support unless
  live testing shows one of them is immediately necessary.

After the end-to-end loop is stable, read-only Factorio tools can be designed as
explicit structured operations. Any material in-game action will require a
separate safety design and will remain restricted to `dlbattle`.
