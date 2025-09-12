# Correctness Validation Checklist for Codex Plus

## ⚠️ CRITICAL RUNTIME FIXES REQUIRED

### 1. Headers Variable Definition Order (SEVERITY 1)
**File**: `src/codex_plus/llm_execution_middleware.py`  
**Lines**: 215, 219

```python
# ❌ BROKEN: headers used before definition
if hasattr(request, 'state') and getattr(request.state, 'modified_body', None):
    body = request.state.modified_body
    headers['content-length'] = str(len(body))  # NameError!
    logger.info("Using body from pre-input hooks")
except Exception as e:
    logger.debug(f"Unable to read modified_body: {e}")
headers = dict(request.headers)  # Defined AFTER usage

# ✅ FIXED: Move headers definition before usage
headers = dict(request.headers)
if hasattr(request, 'state') and getattr(request.state, 'modified_body', None):
    body = request.state.modified_body
    headers['content-length'] = str(len(body))
    logger.info("Using body from pre-input hooks")
```

### 2. Content-Length Synchronization (SEVERITY 2)
**File**: `src/codex_plus/llm_execution_middleware.py`  
**Lines**: 264, 215

```python
# ❌ PROBLEMATIC: Content-Length may be incorrect
if len(modified_body) != len(body):
    headers['content-length'] = str(len(modified_body))

# ✅ VALIDATED: Ensure header matches actual body
actual_length = len(modified_body)
headers['content-length'] = str(actual_length)
# Verify the body being sent matches the header
assert len(body) == actual_length, f"Body length {len(body)} != header {actual_length}"
```

### 3. Error Status Code Preservation (SEVERITY 2)  
**File**: `src/codex_plus/llm_execution_middleware.py`

```python
# ❌ BROKEN: All errors become 500
except Exception as e:
    logger.error(f"Proxy request failed: {e}")
    return JSONResponse(
        content={"error": f"Proxy failed: {str(e)}"},
        status_code=500
    )

# ✅ FIXED: Preserve upstream status codes
except requests.RequestException as e:
    # Extract status code from upstream response if available
    status_code = getattr(e.response, 'status_code', 502)
    error_content = getattr(e.response, 'text', str(e)) if hasattr(e, 'response') else str(e)
    return JSONResponse(
        content={"error": error_content},
        status_code=status_code
    )
except Exception as e:
    logger.error(f"Proxy request failed: {e}")
    return JSONResponse(
        content={"error": "Internal proxy error"},
        status_code=500
    )
```

## 🔍 CORRECTNESS VALIDATION PATTERNS

### Input Validation Requirements

```python
# ✅ VALIDATE: Content-Type before JSON parsing
content_type = headers.get('content-type', '')
if body and 'application/json' in content_type:
    try:
        data = json.loads(body)
        # Process JSON
    except json.JSONDecodeError:
        logger.warning("Invalid JSON despite Content-Type")
        # Handle gracefully
else:
    # Handle non-JSON bodies appropriately
```

### State Management Corrections

```python
# ❌ INCORRECT: request.state always exists in FastAPI
if hasattr(request, 'state') and getattr(request.state, 'modified_body', None):

# ✅ CORRECT: Check for specific attribute
if getattr(request.state, 'modified_body', None) is not None:
```

### Concurrent Session Safety

```python
# ❌ UNSAFE: Shared session across requests  
if not hasattr(self, '_session'):
    self._session = requests.Session(impersonate="chrome124")
session = self._session

# ✅ SAFER: Per-request session or proper locking
def get_session(self):
    with self._session_lock:
        if not hasattr(self, '_session'):
            self._session = requests.Session(impersonate="chrome124")
        return self._session
```

### Subprocess Security

```python
# ❌ RISKY: Environment variable expansion
cmd_expanded = shlex.split(_os.path.expandvars(cmd_str))

# ✅ SAFER: Validate environment variables first
safe_env_vars = {'CLAUDE_PROJECT_DIR', 'HOME', 'USER'}
if any(f'${var}' in cmd_str for var in os.environ if var not in safe_env_vars):
    raise ValueError("Unsafe environment variable in command")
cmd_expanded = shlex.split(_os.path.expandvars(cmd_str))
```

## 🧪 TESTING REQUIREMENTS FOR CORRECTNESS

### Critical Test Cases

1. **Headers Consistency Tests**
   ```python
   def test_headers_content_length_consistency():
       # Test modified body updates content-length correctly
       # Test original body preserves content-length
   ```

2. **Error Passthrough Tests**
   ```python
   @pytest.mark.parametrize("status_code", [401, 403, 429, 502, 503])
   def test_upstream_error_preservation(status_code):
       # Verify upstream status codes are preserved
   ```

3. **Boundary Condition Tests**
   ```python
   def test_empty_body_handling():
   def test_malformed_json_handling():  
   def test_binary_body_handling():
   def test_large_body_handling():
   ```

4. **State Management Tests**
   ```python
   def test_concurrent_request_isolation():
   def test_modified_body_state_handling():
   ```

## 📋 PRE-COMMIT CORRECTNESS CHECKLIST

- [ ] **Variable Definitions**: All variables defined before first use
- [ ] **Header Consistency**: Content-Length matches actual body size  
- [ ] **Error Handling**: Upstream status codes preserved
- [ ] **Input Validation**: Content-Type checked before parsing
- [ ] **State Safety**: Request state accessed safely
- [ ] **Concurrency**: Shared resources properly synchronized
- [ ] **Test Coverage**: All error paths and edge cases tested

## 🚨 IMMEDIATE ACTION REQUIRED

The headers variable bug (Severity 1) will cause `NameError` crashes on normal operation. This must be fixed before any PR merge.

Run this to verify the fix:
```bash
# Test that modified body handling works
python -c "
import json
from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware
middleware = LLMExecutionMiddleware('test')
# This should not crash with NameError
"
```

## 📊 CORRECTNESS METRICS

Track these metrics for correctness validation:
- **Error Rate**: % of requests resulting in 5xx errors  
- **Status Code Accuracy**: % of upstream error codes preserved
- **Content-Length Mismatches**: Count of responses with incorrect headers
- **Concurrent Request Failures**: Count of race condition errors
- **Memory Usage**: Track streaming vs buffering behavior

## 🔄 CONTINUOUS CORRECTNESS VALIDATION

Add these automated checks:
1. **Static Analysis**: MyPy type checking for variable scoping
2. **Integration Tests**: Real HTTP client testing error scenarios  
3. **Load Testing**: Concurrent request correctness under load
4. **Boundary Testing**: Automated fuzzing for edge cases
5. **Security Scanning**: Command injection and input validation checks