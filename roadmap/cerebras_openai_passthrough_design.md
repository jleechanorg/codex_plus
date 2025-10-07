# Cerebras Passthrough Debugging Notes

## Tool Output Capture

- Added `/tmp/codex_plus/cereb_conversion/tool_outputs_*.json` snapshots that
  capture the Codex CLI follow-up request after a tool call.  The logger removes
  `Authorization`/`Cookie` headers and writes the sanitized payload using
  `asyncio.to_thread` so the proxy hot-path stays non-blocking.
- These records allow us to confirm whether the CLI submits tool output payloads
  and inspect their format while we continue aligning the Cerebras handler with
  OpenAI's `/responses` contract.
- Each snapshot includes the request path and raw JSON body to make it easy to
  diff against the ChatGPT baseline responses captured under
  `/tmp/codex_plus/chatgpt_responses/`.

## Next Steps

- Wire the captured payloads into the Cerebras translator so `/responses/{id}/tool_outputs`
  can be replayed against `chat/completions` without manual intervention.
- Once the upstream call succeeds, emit the matching
  `response.function_call_arguments.*` and `response.output_item.*` events so the
  Codex CLI resumes execution automatically.
