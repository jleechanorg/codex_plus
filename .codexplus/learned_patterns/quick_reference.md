# Fake Code Detection - Quick Reference

## Pattern Detection Commands

```bash
# Search for bare except statements (HIGH priority)
grep -r "except:" src/ test/ .codexplus/ | grep -v "__pycache__"

# Find single-line Python files (CRITICAL priority)
find . -name "*.py" -exec wc -l {} + | grep "^ *1 " | awk '{print $2}'

# Look for debugging markers
grep -r "open.*tmp.*write" . --include="*.py"

# Find TODO/FIXME patterns
grep -r "TODO\|FIXME\|would be implemented" . --include="*.py"
```

## Critical Patterns to Watch

1. **Debugging Stubs**: Single-line files with debug operations
2. **Silent Exceptions**: `except: pass` without logging
3. **Unclear Placeholders**: Comments without implementation context
4. **Test Cleanup**: Bare except in teardown methods

## Red Flags

- Files under 5 lines in production directories
- Exception handlers without logging
- Temporary file operations in production code
- Comments mentioning "would be implemented"

## Prevention

- Code review checklist for exception handling
- Automated linting for bare except statements
- Regular /fake3 audits
- Clear documentation standards