# Jimbo Local Factorio Bot

## Goal

Build a lightweight, fully local Factorio chat bot that players can address in
public chat without consuming Codex or other hosted-model quota. The bot should
run alongside the game and dedicated server without materially competing for
their resources.

The first milestone is a small, reliable conversational bot. Game-awareness
and carefully bounded RCON actions can be added after the chat loop works.

## Constraints and decisions

- Do not require a Factorio mod.
- Read player chat from
  `D:\factorio-server\server-console.log`.
- Send replies and later game queries/actions through the repository's fixed
  RCON wrapper at `tools/factorio-rcon.ps1`.
- Run inference locally. Routine bot use must not call Codex or a cloud model.
- Make the bot publicly available to all players.
- A message gets the bot's attention when it contains the complete word
  `jimbo`, case-insensitively. No punctuation or special command prefix is
  required.
- Keep the first implementation simple. Spam precautions must not make normal
  use awkward or significantly slow development.

## Proposed architecture

```text
Factorio public chat
        |
        v
server-console.log tailer
        |
        v
message parser and whole-word "jimbo" trigger
        |
        v
short per-player conversation history
        |
        v
local Ollama API -> Qwen3 1.7B (4-bit, non-thinking)
        |
        v
serialized RCON reply -> Factorio public chat
```

The bot should store a durable log cursor so a restart does not replay old chat
messages. It should parse the player name and message from `[CHAT]` records,
then ignore server events, join/leave records, and malformed lines.

## Model and runtime

Initial choice:

- Runtime: Ollama, accessed through its local HTTP API.
- Model: Qwen3 1.7B using a 4-bit quantization.
- Thinking mode: disabled.
- Context window: start at 2,048 to 4,096 tokens.
- Maximum response: approximately 80 tokens, with an additional Factorio chat
  length check before sending.
- Concurrency: one generation at a time so inference cannot multiply resource
  use during busy chat.
- Conversation memory: retain only the most recent 4 to 6 exchanges per player.

If Qwen3 1.7B is unexpectedly heavy, Qwen3 0.6B is the fallback, with the
expectation of lower conversation quality and instruction reliability.

## Trigger and response behavior

Examples that should trigger the bot:

- `Jimbo who is online?`
- `hey jimbo, what should we build next?`
- `can you check power, Jimbo`

Text such as `jimbob` must not trigger it. The parser should remove the
attention word and nearby conversational punctuation before sending the request
to the model. If nothing meaningful remains, the bot can respond with a short
greeting or ask what the player needs.

The bot will initially reply publicly. It must recognize and ignore its own
RCON-generated output so it cannot enter a response loop even when its answer
contains the word `Jimbo`.

## Minimal safeguards

For the first working version:

- Allow only one queued or active request per player.
- Add a short per-player cooldown intended only to stop rapid accidental spam.
- Bound the global queue so a burst cannot consume unlimited memory or keep the
  model busy indefinitely.
- Limit prompt history and output length.
- Never treat model-generated text as Lua, PowerShell, or an RCON command.
- Keep world-changing actions disabled in the initial chat milestone.
- Record parsed requests, model responses, errors, and RCON results locally for
  diagnosis.

These controls should use clear defaults and should not require accounts,
permissions, or special chat syntax.

## Future game integration

After basic public chat is proven, add explicit structured tools rather than
giving the model arbitrary RCON access. Likely read-only tools include listing
online players, checking a named surface, and inspecting selected production or
power statistics.

Any later world-changing tools should be allowlisted, validate all inputs, and
follow the repository's placement rules. Material actions should remain
restricted to `dlbattle`, while ordinary conversation and safe queries can stay
publicly available. The model should choose a structured tool and arguments;
application code should construct and validate the actual RCON command.

## First implementation milestone

1. Confirm Ollama is installed and the selected model can answer a short local
   prompt without excessive resource use.
2. Tail only new records from `server-console.log` and persist the cursor.
3. Parse public chat and detect the whole word `jimbo`.
4. Generate a short non-thinking response with Qwen3 1.7B.
5. Send that response to Factorio through the existing fixed RCON wrapper.
6. Verify that the bot ignores its own response and resumes watching for new
   messages after a restart.

## Open implementation choices

- Exact Python version and dependency strategy.
- Whether to invoke the existing PowerShell RCON wrapper directly or factor a
  narrowly scoped reusable helper around it while preserving its credential
  handling.
- The precise server-log cursor format and rotation handling.
- Public reply formatting, including whether to prefix replies with `Jimbo:` or
  address the requesting player by name.
- Default cooldown, queue size, model idle-unload behavior, and startup method.
