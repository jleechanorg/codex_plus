# TODO: Test Real ChatGPT Response Format

## ⏰ When Usage Limit Resets (~4.5 hours from 2025-10-01 03:20 UTC)

### Action Items

1. **Start proxy in ChatGPT mode** (NOT Cerebras):
   ```bash
   ./proxy.sh restart  # Defaults to ChatGPT mode
   ```

2. **Run test tasks to capture responses**:
   ```bash
   export OPENAI_BASE_URL=http://localhost:10000

   # Test 1: Simple text response
   codex exec --yolo 'echo "hello world"'

   # Test 2: File creation (tool call)
   codex exec --yolo 'create /tmp/test.py that prints fibonacci'

   # Test 3: Multiple operations
   codex exec --yolo 'create /tmp/calc.py with add/subtract, then test it'
   ```

3. **Analyze captured responses**:
   ```bash
   cat /tmp/codex_plus/chatgpt_responses/latest_response.txt
   ```

4. **Validate against research findings**:
   - Check event types match: `response.output_text.delta`
   - Check function call format: `response.function_call.arguments.delta`
   - Verify flat `delta` field (not nested)
   - Compare with docs/chatgpt_response_format_analysis.md

5. **Update transformation if needed**:
   - If format differs from research, update `src/codex_plus/llm_execution_middleware.py`
   - Document any discrepancies in `roadmap/cerebras_tool_calling_investigation.md`

## 📊 Expected Event Types (Based on Research)

### Text Response
```json
{"type": "response.created", "response": {"id": "...", "status": "in_progress"}}
{"type": "response.output_item.added", "item": {...}}
{"type": "response.output_text.delta", "delta": "text chunk"}
{"type": "response.completed", "response": {"id": "...", "status": "completed"}}
```

### Tool Call Response
```json
{"type": "response.created", "response": {"id": "...", "status": "in_progress"}}
{"type": "response.output_item.added", "item": {...}}
{"type": "response.function_call.arguments.delta", "delta": "{\"command\":"}
{"type": "response.function_call.arguments.delta", "delta": " [\"bash\","}
...
{"type": "response.completed", "response": {"id": "...", "status": "completed"}}
```

## 🎯 Success Criteria

- [ ] Captured at least 3 different response types
- [ ] Event types match research documentation
- [ ] Tool calls show correct format
- [ ] Text deltas use flat structure
- [ ] Documented any format differences

## 📝 Files to Create

After capturing:
- `docs/chatgpt_response_format_analysis.md` - Detailed analysis
- `docs/chatgpt_response_examples/` - Raw response files
  - `text_response.txt`
  - `tool_call_response.txt`
  - `multi_tool_response.txt`

## ⚠️ Current Implementation Status

**Before Real Response Testing:**
- Implemented format based on documentation research
- Event types: `response.output_text.delta`, `response.function_call.arguments.delta`
- Flat delta structure (not nested)
- Testing with Cerebras first to validate transformation logic

**After Real Response Testing:**
- Compare actual vs expected format
- Adjust if discrepancies found
- Mark as validated in commit message
