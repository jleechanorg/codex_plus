# Test: Tool Calling

**Objective**: Test function calling through Cerebras proxy with tool transformation

**Category**: Medium (30-60 seconds)

**Prerequisites**:
- Tests 01-03 passed
- Cerebras supports function calling
- Tool format transformation works

## Commands to Execute

### 1. Simple Shell Command via Tool
```bash
echo "Use the shell tool to run 'echo hello' and show me the output." | \
  OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo
```

**Expected**: Tool called, command executed, output shown

### 2. Verify Tool Transformation in Logs
```bash
grep "tool\|function" /tmp/codex_plus/proxy.log | tail -15
```

**Expected**: Evidence of tool format transformation (flat → nested)

## Validation Criteria

- [ ] Tool call was made successfully
- [ ] Shell command executed
- [ ] Output returned correctly ("hello")
- [ ] Logs show tool transformation
- [ ] No tool calling errors

## Evidence Requirements

**Save to**: `/tmp/codex_plus/cereb_conversion/test_evidence/04_tool_calling/`

### Files

1. **`command_output.txt`** - Full execution output

2. **`validation.json`**:
```json
{
  "test_name": "04_tool_calling",
  "status": "PASS",
  "timestamp": "<ISO 8601>",
  "criteria": [
    {"name": "Tool called", "passed": true},
    {"name": "Command executed", "passed": true},
    {"name": "Correct output", "passed": true},
    {"name": "Tool transformation detected", "passed": true},
    {"name": "No errors", "passed": true}
  ],
  "tool_evidence": "Found in logs",
  "output_preview": "hello"
}
```

3. **`summary.md`** - Report with tool calling details

## Execution Steps

1. Create evidence directory:
```bash
EVIDENCE_DIR="/tmp/codex_plus/cereb_conversion/test_evidence/04_tool_calling"
mkdir -p "$EVIDENCE_DIR"
```

2. Execute tool calling request:
```bash
echo "Use the shell tool to run 'echo hello' and show me the output." | \
  OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo \
  > "$EVIDENCE_DIR/command_output.txt" 2>&1
```

3. Extract tool transformation evidence:
```bash
echo "\n=== Tool Transformation Evidence ===" >> "$EVIDENCE_DIR/command_output.txt"
grep -A 3 -B 3 "tool\|function" /tmp/codex_plus/proxy.log | tail -20 \
  >> "$EVIDENCE_DIR/command_output.txt"
```

4. Validate:
   - Output contains "hello"
   - No tool calling errors
   - Logs show transformation

5. Create validation.json and summary.md

## Success Indicators

✅ **Pass if**:
- Shell tool invoked successfully
- Command output visible
- Tool transformation evidence in logs
- No errors

❌ **Fail if**:
- Tool call rejected or not made
- Command not executed
- Missing transformation evidence
- Any tool calling errors

## Notes

This test validates that:
- Codex tool format → Cerebras function format transformation works
- Cerebras supports function calling
- Tool results flow back correctly
