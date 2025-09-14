# 01 Basic Proxy Test

## Objective
Verify that the Codex Plus proxy server is running correctly and can handle basic requests.

## Prerequisites
- Python 3.8+ installed
- Virtual environment activated
- Dependencies installed (`pip install -r requirements.txt`)

## Test Steps

### 1. Start the Proxy Server

```bash
# Navigate to project root
cd /Users/jleechan/projects_other/codex_plus

# Start the proxy server
./proxy.sh enable

# Verify it's running
./proxy.sh status
```

**Expected Result**:
- Server starts on localhost:3000
- Status shows "Running" with PID
- No error messages in the console

### 2. Test Health Endpoint

```bash
# Test health endpoint
curl -v http://localhost:3000/health
```

**Expected Result**:
```json
{"status": "healthy"}
```
- HTTP 200 response
- JSON response with status "healthy"

### 3. Test Request Forwarding (Will Get 401)

```bash
# Test basic request forwarding (expect 401 since no auth)
curl -X POST http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{
    "model": "claude-3",
    "messages": [{"role": "user", "content": "test"}]
  }' -v
```

**Expected Result**:
- HTTP 401 Unauthorized (this is expected - means proxy is forwarding correctly)
- Response should come from upstream ChatGPT backend
- Proxy logs should show the request being processed

### 4. Check Proxy Logs

```bash
# Check proxy logs for request processing
tail -n 20 proxy.log
```

**Expected Result**:
- Log entries showing request processing
- No error messages about hook loading failures
- Status line generation attempts (if in git repo)

### 5. Test Git Status Line Generation

```bash
# Check if git status line is generated
grep -i "git status" proxy.log | tail -5
```

**Expected Result**:
- Log entries showing git status line generation
- Should show current branch, sync status, etc.

## Success Criteria Checklist

- [ ] Proxy server starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] Request forwarding works (gets 401 from upstream)
- [ ] Proxy logs show request processing
- [ ] No hook loading errors in logs
- [ ] Git status line generation works

## Cleanup

```bash
# Stop the proxy server
./proxy.sh disable

# Verify it's stopped
./proxy.sh status
```

## Troubleshooting

**If server won't start**:
- Check if port 3000 is already in use: `lsof -i :3000`
- Check Python dependencies: `pip list | grep -E "(fastapi|curl_cffi|uvicorn)"`
- Review any error messages in the terminal

**If health endpoint fails**:
- Verify server is actually running: `ps aux | grep uvicorn`
- Check if firewall is blocking port 3000
- Try using 127.0.0.1 instead of localhost

**If git status fails**:
- Ensure you're in a git repository
- Check git is installed and working: `git --version`
- Verify `.codexplus/settings.json` or `.claude/settings.json` exists