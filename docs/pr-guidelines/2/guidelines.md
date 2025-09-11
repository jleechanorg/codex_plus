# PR #2 Guidelines - Slash Command System Implementation

**PR**: #2 - feat: Add slash command system with .claude/ infrastructure integration
**Created**: 2025-09-10
**Review Focus**: Bugs, Correctness, and Unneeded Code

## 🎯 PR-Specific Principles

Based on comprehensive review, these principles emerged from analyzing this PR:

1. **Single Implementation Principle**: Avoid duplicate implementations of the same functionality
2. **Resource Lifecycle Management**: Always ensure cleanup of resources in streaming/generator contexts
3. **Input Validation First**: Validate and sanitize all user inputs before processing
4. **Explicit Error Boundaries**: Define clear error handling strategies for different failure modes
5. **Configuration Centralization**: Keep configuration in one place, not scattered across files

## 🚫 PR-Specific Anti-Patterns

### ❌ **Infinite Loop in While Iteration**
**Found in**: enhanced_slash_middleware.py:376-411

```python
# WRONG - Can cause infinite loop
while i < length:
    m = re.search(pattern, text[i:])
    # ... processing
    i = seg_end  # If seg_end == i, loop never advances
```

### ✅ **Safe Loop Advancement**
```python
# CORRECT - Always guarantee progress
while i < length:
    m = re.search(pattern, text[i:])
    # ... processing
    prev_i = i
    i = seg_end
    if i <= prev_i:  # Safety check
        i = prev_i + 1  # Force advancement
```

---

### ❌ **Resource Leak in Generators**
**Found in**: slash_command_middleware.py:374-382

```python
# WRONG - Cleanup in generator may not execute
def stream_response():
    try:
        for chunk in response.iter_content():
            yield chunk
    finally:
        response.close()
        session.close()  # May never run if generator abandoned
```

### ✅ **Proper Resource Management**
```python
# CORRECT - Manage resources outside generator
def create_streaming_response():
    session = create_session()
    response = session.get(url, stream=True)
    
    def generate_with_cleanup():
        try:
            for chunk in response.iter_content():
                yield chunk
        finally:
            response.close()
    
    # Return wrapper that ensures cleanup
    return GeneratorWithCleanup(generate_with_cleanup(), session)
```

---

### ❌ **Path Traversal Vulnerability**
**Found in**: slash_command_middleware.py:169-176

```python
# WRONG - No input validation
command_file = self.commands_dir / f"{command_name}.md"
```

### ✅ **Secure Path Construction**
```python
# CORRECT - Validate input first
import re
if not re.match(r'^[a-zA-Z0-9_-]+$', command_name):
    raise ValueError(f"Invalid command name: {command_name}")
command_file = self.commands_dir / f"{command_name}.md"

# Even better - use safe resolution
base_path = Path(self.commands_dir).resolve()
requested_file = (base_path / f"{command_name}.md").resolve()
if not str(requested_file).startswith(str(base_path)):
    raise SecurityError("Path traversal attempt detected")
```

---

### ❌ **Duplicate Implementation**
**Found in**: Two complete middleware implementations

```python
# WRONG - Two files with 90% identical code
# slash_command_middleware.py (622 lines)
# enhanced_slash_middleware.py (481 lines)
```

### ✅ **Single Source of Truth**
```python
# CORRECT - One implementation with configuration options
class SlashCommandMiddleware:
    def __init__(self, mode='enhanced'):
        self.mode = mode
        # Single implementation with mode-specific behavior
```

---

### ❌ **Unbounded Regex on User Input**
**Found in**: Both middleware files

```python
# WRONG - ReDoS vulnerability
re.search(r'/(?:[A-Za-z0-9_-]+)', entire_request_body)
```

### ✅ **Bounded Input Processing**
```python
# CORRECT - Limit input size and use simple patterns
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB
if len(request_body) > MAX_BODY_SIZE:
    raise ValueError("Request body too large")

# Use simple, non-backtracking patterns
pattern = re.compile(r'/[A-Za-z0-9_-]+')  # No nested quantifiers
```

## 📋 Implementation Patterns for This PR

### Successful Patterns Identified

1. **Command Registry Pattern** (enhanced_slash_middleware.py)
   - Clean separation of command discovery and execution
   - Extensible design for adding new commands

2. **YAML Frontmatter for Metadata** (slash_command_middleware.py)
   - Good use of structured metadata for command configuration
   - Clear separation of documentation and implementation

3. **Streaming Response Handling** (when done correctly)
   - Efficient memory usage for large responses
   - Proper use of curl_cffi for Cloudflare bypass

## 🔧 Specific Implementation Guidelines

### For Fixing This PR

1. **Choose One Middleware**
   - Keep `EnhancedSlashCommandMiddleware` (better architecture)
   - Remove `SlashCommandMiddleware` to eliminate duplication
   - Migrate any unique features from classic to enhanced

2. **Fix Critical Bugs First**
   - Add loop safety check (line 411)
   - Fix resource cleanup in generators
   - Add input validation for command names
   - Implement request size limits

3. **Extract Shared Components**
   ```python
   # Create http_proxy.py
   class HttpProxy:
       def __init__(self, upstream_url):
           self.upstream_url = upstream_url
           self.session_pool = SessionPool()
       
       async def forward_request(self, request):
           # Shared proxy logic here
   ```

4. **Centralize Configuration**
   ```python
   # Create config.py
   @dataclass
   class ProxyConfig:
       upstream_url: str = "https://chatgpt.com/backend-api/codex"
       max_body_size: int = 10_485_760  # 10MB
       request_timeout: int = 30
       browser_impersonate: str = "chrome124"
   ```

5. **Implement Proper Testing**
   - Add tests for error paths
   - Test resource cleanup scenarios
   - Add security test cases for path traversal
   - Test with malformed input

## 🛡️ Security Checklist

- [ ] Validate all user inputs against whitelist patterns
- [ ] Implement request size limits
- [ ] Use bounded, simple regex patterns
- [ ] Ensure proper resource cleanup in all code paths
- [ ] Validate file paths stay within intended directories
- [ ] Handle JSON parsing errors gracefully
- [ ] Don't expose internal errors to clients

## 📊 Metrics to Track

- **Code Duplication**: Reduce from 40% to <5%
- **Method Length**: No method >30 lines
- **Cyclomatic Complexity**: Keep below 10 per method
- **Test Coverage**: Achieve >80% for critical paths
- **Security Scan**: Zero high-severity vulnerabilities

---

**Status**: Guidelines created from /reviewdeep analysis
**Last Updated**: 2025-09-10

## Lessons Learned

1. **Dual implementations create more problems than they solve** - The attempt to maintain backward compatibility led to massive code duplication
2. **Generators need special care for resource management** - Standard try/finally doesn't work as expected
3. **Input validation is not optional** - Every user input is a potential security vulnerability
4. **Complex regex on user input is dangerous** - Simple patterns and size limits prevent ReDoS
5. **Configuration should be centralized** - Scattered magic values make systems hard to maintain