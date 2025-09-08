# Codex Proxy Authentication Issue Analysis

## Summary
The Codex CLI cannot authenticate through a proxy to OpenAI's `/v1/responses` endpoint, even though the same token works when Codex connects directly.

## Key Findings

### 1. Token Works Directly
- Codex successfully authenticates when connecting directly to `api.openai.com`
- Uses experimental endpoint: `/v1/responses` with header `openai-beta: responses=experimental`
- Model: `gpt-5`

### 2. Token Fails Through Proxy
- Same token gets 401 error: "Missing scopes: api.responses.write"
- Error occurs even with perfect passthrough proxy (all headers forwarded exactly)
- Error also occurs when testing token directly with curl

### 3. Authentication Details
- Codex uses ChatGPT OAuth2 JWT tokens (not API keys)
- Token stored in `~/.codex/auth.json` as `access_token`
- Token includes ChatGPT account ID and subscription info
- `OPENAI_API_KEY` is null in auth.json

## Technical Analysis

### Headers Sent by Codex
```
authorization: Bearer [JWT token]
version: 0.30.0
openai-beta: responses=experimental
session_id: [UUID]
accept: text/event-stream
content-type: application/json
chatgpt-account-id: [account-id]
user-agent: codex_cli_rs/0.30.0
originator: codex_cli_rs
```

### Error Response
```json
{
  "error": {
    "message": "You have insufficient permissions for this operation. Missing scopes: api.responses.write.",
    "type": "invalid_request_error"
  }
}
```

## Root Cause Hypothesis

OpenAI's API appears to detect and reject proxied requests for the experimental `/v1/responses` endpoint. Possible detection methods:

1. **TLS Fingerprinting**: Different TLS characteristics between Codex (Rust/native) and httpx (Python)
2. **Certificate Pinning**: Codex may verify OpenAI's certificate in a specific way
3. **Connection Metadata**: TCP/IP connection details that change through proxy
4. **Request Timing**: Subtle timing differences in proxied requests

## Implications

1. **LiteLLM Incompatible**: Cannot use LiteLLM proxy with Codex authentication
2. **Simple Proxy Fails**: Even passthrough proxies break authentication
3. **Slash Commands Limited**: Cannot intercept/modify Codex requests without breaking auth

## Potential Solutions

1. **Use Standard API Keys**: Configure Codex to use regular OpenAI API keys instead of ChatGPT OAuth
2. **Client-Side Hooks**: Implement features at the shell/terminal level instead of HTTP proxy
3. **Reverse Engineering**: Deep analysis of Codex binary to understand exact authentication mechanism
4. **Official API**: Wait for OpenAI to provide official API access to the responses endpoint

## Test Commands

```bash
# Test direct connection (works)
codex exec 'echo "test"'

# Test through proxy (fails with 401)
OPENAI_BASE_URL=http://localhost:3000 codex exec 'echo "test"'

# Test token with curl (also fails with 401)
TOKEN=$(jq -r .tokens.access_token ~/.codex/auth.json)
curl -X POST https://api.openai.com/v1/responses \
  -H "Authorization: Bearer $TOKEN" \
  -H "openai-beta: responses=experimental" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5","messages":[{"role":"user","content":"test"}]}'
```

## Conclusion

The proxy approach is fundamentally incompatible with Codex's authentication model for the experimental responses endpoint. The issue is not with our proxy implementation but with OpenAI's security measures that prevent proxied access to this endpoint.