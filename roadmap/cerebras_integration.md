# Cerebras Integration Design

## Problem Statement

Codex-Plus proxy currently forwards requests directly to upstream, but Codex CLI and Cerebras API use incompatible formats:

- **Codex CLI**: Custom `/responses` endpoint with nested message structures and proprietary fields
- **Cerebras API**: Standard OpenAI `/v1/chat/completions` format with flat message objects

**Current Status**: ✅ Routing works, ❌ Format incompatible → 404 errors

## Solution Architecture

### High-Level Design

```
Codex CLI → Proxy → [Format Transformer] → Cerebras API
                         ↓
              - Endpoint mapping
              - Request transformation
              - Response transformation
```

### Component Design

#### 1. Provider Detection Layer
**Location**: `src/codex_plus/main_sync_cffi.py`

```python
provider_mode = os.getenv("CODEX_PLUS_PROVIDER_MODE", "openai")
# "openai" → Direct passthrough (current behavior)
# "cerebras" → Apply format transformation
```

#### 2. Request Transformer
**Location**: `src/codex_plus/cerebras_transformer.py` (new file)

**Core Transformations**:
- `instructions` field → system message in `messages[]`
- `input[]` nested structure → flat `messages[]`
- Extract text: `content[{type: "input_text", text}]` → `content: text`
- Restructure tools: `{type, name, ...}` → `{type, function: {name, ...}}`
- Map endpoints: `/responses` → `/v1/chat/completions`
- Drop unsupported fields: `reasoning`, `store`, `include`, `prompt_cache_key`, `strict`

**Class Structure**:
```python
class CodexToCerebrasTransformer:
    def transform_request(self, codex_request: dict) -> dict:
        """Convert Codex format to Cerebras/OpenAI format"""

    def transform_messages(self, instructions: str, input: list) -> list:
        """Merge instructions and input into messages array"""

    def transform_tools(self, codex_tools: list) -> list:
        """Restructure tools to OpenAI nested format"""

    def transform_response(self, cerebras_response: dict) -> dict:
        """Convert Cerebras response back to Codex format (if needed)"""
```

#### 3. Middleware Integration
**Location**: `src/codex_plus/llm_execution_middleware.py`

**Injection Point**: `process_request()` method before forwarding

```python
# In LLMExecutionMiddleware.process_request()
if self.provider_mode == "cerebras":
    transformer = CodexToCerebrasTransformer()
    body = transformer.transform_request(json.loads(body))
    target_url = f"{self.upstream_url}/chat/completions"  # Map endpoint
    headers = transformer.transform_headers(headers)  # API key auth
```

## Implementation Phases

### Phase 1: Request Transformation (MVP)
**Files**:
- `src/codex_plus/cerebras_transformer.py` - New transformer class
- `tests/test_cerebras_transformer.py` - Comprehensive unit tests

**Deliverables**:
- ✅ Message format transformation
- ✅ Tools format transformation
- ✅ Endpoint mapping
- ✅ Field filtering (drop unsupported)
- ✅ Unit tests with 100% coverage

**Acceptance Criteria**:
- All tests pass
- Sample Codex request transforms correctly
- No regressions in OpenAI passthrough mode

### Phase 2: Middleware Integration
**Files**:
- `src/codex_plus/llm_execution_middleware.py` - Add transformation logic
- `src/codex_plus/main_sync_cffi.py` - Provider mode detection

**Deliverables**:
- ✅ Provider mode detection from env/file
- ✅ Conditional transformation in middleware
- ✅ Authentication header transformation
- ✅ Integration tests

**Acceptance Criteria**:
- Cerebras requests succeed and return valid responses
- OpenAI/ChatGPT mode continues to work unchanged
- Provider switching works without restart

### Phase 3: Response Transformation (Optional)
**Files**:
- `src/codex_plus/cerebras_transformer.py` - Response transformer

**Deliverables**:
- ⚠️ Response format compatibility check
- ⚠️ Transform if Codex CLI expects different format

**Decision Point**: Only implement if Codex CLI rejects Cerebras responses

### Phase 4: Edge Cases & Optimization
**Deliverables**:
- Handle multimodal content (images, files)
- Error handling for transformation failures
- Logging and debugging tools
- Performance profiling

## Technical Specifications

### Request Transformation Rules

| Codex Field | Cerebras Field | Transformation |
|-------------|----------------|----------------|
| `model: "gpt-5-codex"` | `model: "llama-3.3-70b"` | Model name mapping |
| `instructions: "..."` | `messages[0]: {role: "system", content: "..."}` | Merge as system message |
| `input: [{type: "message", role, content}]` | `messages: [{role, content}]` | Flatten structure |
| `content: [{type: "input_text", text}]` | `content: "text"` | Extract text |
| `tools: [{type, name, parameters}]` | `tools: [{type, function: {name, parameters}}]` | Nest under `function` |
| `reasoning: {...}` | *(drop)* | Not supported |
| `store: bool` | *(drop)* | Not supported |
| `include: []` | *(drop)* | Not supported |
| `prompt_cache_key` | *(drop)* | Not supported |
| `tool_choice: "auto"` | `tool_choice: "auto"` | Pass through |
| `stream: true` | `stream: true` | Pass through |

### Endpoint Mapping

```python
ENDPOINT_MAP = {
    "openai": {
        "/responses": "/backend-api/codex/responses",
        # ... other endpoints
    },
    "cerebras": {
        "/responses": "/v1/chat/completions",
        # ... other endpoints
    }
}
```

## Testing Strategy

### Unit Tests
- ✅ Message transformation with various input types
- ✅ Tool transformation with nested parameters
- ✅ Field filtering (drop unsupported)
- ✅ Model name mapping
- ✅ Edge cases: empty input, missing fields, malformed data

### Integration Tests
- ✅ Full request transformation with real Codex payload
- ✅ Middleware injection and forwarding
- ✅ Provider mode switching
- ✅ Authentication header transformation

### End-to-End Tests
- ✅ Actual Cerebras API call (requires API key)
- ✅ Response handling and streaming
- ✅ Tool calls with Cerebras

## Risks & Mitigations

### Risk 1: Response Format Incompatibility
**Impact**: High - Codex CLI may reject Cerebras responses
**Likelihood**: Medium
**Mitigation**:
- Test with real Codex CLI first
- Implement response transformer if needed
- Monitor error logs

### Risk 2: Tool Calling Differences
**Impact**: High - Tool execution may fail
**Likelihood**: Medium
**Mitigation**:
- Verify Cerebras tool calling format
- Test with simple tool calls first
- Fallback to OpenAI if tool calls fail

### Risk 3: Streaming Response Handling
**Impact**: Medium - Streaming may break
**Likelihood**: Low
**Mitigation**:
- Test streaming separately
- Validate SSE format compatibility
- Log streaming errors

### Risk 4: Performance Overhead
**Impact**: Low - Transformation adds latency
**Likelihood**: High
**Mitigation**:
- Profile transformation performance
- Optimize hot paths
- Cache transformed requests if possible

## Success Metrics

- ✅ Cerebras requests return 200 OK (not 404)
- ✅ Codex CLI successfully processes Cerebras responses
- ✅ All tool calls work correctly
- ✅ Streaming responses work without errors
- ✅ < 10ms transformation overhead
- ✅ Zero regressions in OpenAI mode

## References

- **Detailed Technical Spec**: `docs/codex_to_cerebras_transformation.md`
- **Transformation Examples**: `docs/transformation_examples.json`
- **Test Suite**: `tests/test_cerebras_routing.py` (URL validation)
- **Sample Codex Request**: `/tmp/codex_plus/cereb_conversion/request_payload.json`

## Timeline

- **Phase 1 (Request Transformation)**: 1-2 days
- **Phase 2 (Middleware Integration)**: 1 day
- **Phase 3 (Response Transformation)**: 0.5 days (if needed)
- **Phase 4 (Edge Cases)**: 1-2 days

**Total Estimate**: 3-5 days for full Cerebras integration
