# Groq setup for Jimbo

The Groq integration is implemented and tested without a real credential. One
API key is required for the first hosted-model request.

## One-time key handoff

1. Create a Groq API key in the Groq Console.
2. Create this local file:

   ```text
   D:\ChatGPT-Factorio-Playground\factorio-blueprints\jimbo-local-bot\runtime\groq-api-key.txt
   ```

3. Paste only the API key into the file, with no quotes or variable name.
4. Save the file and tell Codex that it is ready. Do not paste the key into chat.

The entire `jimbo-local-bot/runtime/` directory is ignored by Git. The bot reads
the key only to construct the HTTPS `Authorization` header. It does not write
the key to its transcript, console output, RCON payload, or tests.

## First validation

The first real request will be a one-shot console-only comparison using:

- provider: `groq`;
- model: `openai/gpt-oss-120b`;
- prompt: `How do I make green circuits in Factorio?`;
- maximum completion: 256 tokens, including low-effort hidden reasoning;
- reasoning content excluded;
- no Factorio or RCON send.

Only after inspecting that answer will the live watcher be restarted with Groq.
The current Ollama provider remains available as an optional fallback.

## Validation result

Completed on 2026-07-21. The ignored key file was valid and the final
console-only GPT-OSS 120B answer was:

```text
Electronic circuit (green circuit): 1 iron plate + 3 copper cable.
```

No message was sent to Factorio during credential or answer validation.
