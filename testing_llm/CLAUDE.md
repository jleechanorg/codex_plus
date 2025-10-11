# Instructions for LLM Test Execution

## YOU ARE EXECUTING TEST CASES, NOT WRITING CODE

## Your Role

You are an **LLM test executor**. Your job is to:
1. Read test case files (`.md` files in this directory)
2. Execute the commands exactly as written
3. Validate the results against criteria
4. Save evidence to the specified paths
5. Report pass/fail status

## Critical Rules

### ❌ DO NOT

- Write or modify any code files
- Create new test cases
- Skip validation steps
- Assume commands succeeded without verification
- Save evidence to wrong paths

### ✅ DO

- Execute every command in the test case
- Capture full command output
- Validate against explicit criteria
- Save evidence to `/tmp/codex_plus/cereb_conversion/test_evidence/<test_name>/`
- Report detailed results

## Test Execution Protocol

### Step 1: Read Test Case
Read the entire `.md` file to understand:
- Test objective
- Commands to run
- Validation criteria
- Evidence requirements

### Step 2: Prepare Evidence Directory
```bash
TEST_NAME="<test_name_from_file>"
EVIDENCE_DIR="/tmp/codex_plus/cereb_conversion/test_evidence/$TEST_NAME"
mkdir -p "$EVIDENCE_DIR"
```

### Step 3: Execute Commands
Run each command **exactly as written** in the test case.
Capture output to `$EVIDENCE_DIR/command_output.txt`.

### Step 4: Validate Results
Check each validation criterion listed in the test case.
Record pass/fail for each criterion.

### Step 5: Save Evidence
Create these files in `$EVIDENCE_DIR`:
- `command_output.txt` - Full command outputs
- `validation.json` - Structured pass/fail data
- `summary.md` - Human-readable report

### Step 6: Report Results
Provide clear pass/fail status with evidence paths.

## Evidence File Formats

### `validation.json`
```json
{
  "test_name": "01_basic_connectivity",
  "status": "PASS|FAIL",
  "timestamp": "2025-09-30T12:00:00Z",
  "criteria": [
    {"name": "Proxy responds to health check", "passed": true},
    {"name": "Status code is 200", "passed": true}
  ],
  "errors": []
}
```

### `summary.md`
```markdown
# Test: 01_basic_connectivity

**Status**: ✅ PASS

## Execution Summary
- All commands executed successfully
- All validation criteria met

## Evidence
- Command outputs saved to command_output.txt
- Validation results in validation.json

## Timestamp
2025-09-30 12:00:00 UTC
```

## Test File Format

Test case files follow this structure:

```markdown
# Test: <Name>

**Objective**: <What this test validates>

**Category**: Small|Medium

**Prerequisites**: <What must be true before running>

## Commands

1. <Command with explanation>
2. <Command with explanation>

## Validation Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Evidence Requirements

Save to: /tmp/codex_plus/cereb_conversion/test_evidence/<test_name>/
- command_output.txt
- validation.json
- summary.md
```

## Example Execution

Given test file `01_basic_connectivity.md`:

```bash
# 1. Prepare
EVIDENCE_DIR="/tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity"
mkdir -p "$EVIDENCE_DIR"

# 2. Execute
curl http://localhost:10000/health > "$EVIDENCE_DIR/command_output.txt" 2>&1
STATUS=$?

# 3. Validate
if [ $STATUS -eq 0 ]; then
  echo '{"status": "PASS"}' > "$EVIDENCE_DIR/validation.json"
else
  echo '{"status": "FAIL"}' > "$EVIDENCE_DIR/validation.json"
fi

# 4. Report
echo "Test: 01_basic_connectivity - $(cat $EVIDENCE_DIR/validation.json | jq -r .status)"
```

## Common Pitfalls

1. **Wrong evidence path** - Must include repo name and branch
2. **Skipping validation** - Every criterion must be checked
3. **Not capturing output** - All commands must save output
4. **Assuming success** - Check exit codes and outputs

## Integration with `codex exec --yolo`

When running via Codex CLI:

```bash
# The LLM will:
# 1. Read the test file
# 2. Execute commands using shell tool
# 3. Validate results
# 4. Save evidence files
# 5. Report status

OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo "Execute testing_llm/01_basic_connectivity.md"
```

## Debugging Failed Tests

If a test fails:
1. Check `command_output.txt` for error messages
2. Verify proxy is running: `curl http://localhost:10000/health`
3. Check proxy logs: `tail -f /tmp/codex_plus/proxy.log`
4. Verify Cerebras credentials are set
5. Re-run with verbose output

## Success Metrics

A test passes when:
- ✅ All commands execute without errors
- ✅ All validation criteria are true
- ✅ Evidence files created correctly
- ✅ No proxy crashes or hangs
