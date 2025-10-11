# LLM-Driven Test Framework for Cerebras Proxy

This directory contains **LLM-executable test cases** for validating the Cerebras proxy integration. Tests are designed to be run by Codex CLI with `codex exec --yolo`.

## Purpose

Validate Cerebras proxy end-to-end through **real LLM execution**:
- Request transformation (Codex → Cerebras format)
- Proxy forwarding and streaming
- Response handling
- Tool calling through proxy
- Error recovery

## Directory Structure

```text
testing_llm/
├── README.md                   # This file
├── CLAUDE.md                   # LLM execution instructions
├── AGENTS.md                   # Test case catalog
├── 01_basic_connectivity.md    # Small: Proxy health check
├── 02_simple_request.md        # Small: Basic request/response
├── 03_streaming_response.md    # Medium: Streaming validation
├── 04_tool_calling.md          # Medium: Function calling test
└── evidence/                   # Test evidence (gitignored)
```

## Evidence Path

All test evidence saved to:
```text
/tmp/codex_plus/cereb_conversion/test_evidence/<test_name>/
```

## Running Tests

**Prerequisites**:
```bash
# 1. Start proxy in Cerebras mode
./proxy.sh --cerebras

# 2. Verify proxy is running
curl http://localhost:10000/health

# 3. Set environment
export OPENAI_BASE_URL=http://localhost:10000
```

**Execute single test**:
```bash
codex exec --yolo "Read testing_llm/01_basic_connectivity.md and execute it"
```

**Execute all tests**:
```bash
codex exec --yolo "Read testing_llm/AGENTS.md, execute all tests, save evidence"
```

## Test Categories

- **Small** (< 30s): Connectivity, simple requests
- **Medium** (30s-2min): Streaming, tool calling

## Success Criteria

✅ All commands execute without errors
✅ Evidence files created in `/tmp/codex_plus/cereb_conversion/test_evidence/`
✅ Validation criteria met
✅ No proxy crashes

## Evidence Format

Each test produces:
- `command_output.txt` - Full output
- `validation.json` - Pass/fail status
- `summary.md` - Human-readable report
