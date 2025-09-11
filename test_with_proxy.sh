#!/bin/bash

echo "🧪 Testing LLM Execution Middleware with Proxy"
echo "=============================================="
echo ""

# Kill any existing proxy
pkill -f "uvicorn main_sync_cffi:app" 2>/dev/null

echo "1️⃣ Starting proxy with LLM execution middleware..."
export CODEX_PLUS_MIDDLEWARE=llm
export PYTHONPATH=.
nohup uvicorn main_sync_cffi:app --host 127.0.0.1 --port 3000 > proxy_test.log 2>&1 &
PROXY_PID=$!

# Wait for proxy to start
sleep 2

echo "2️⃣ Proxy started (PID: $PROXY_PID)"
echo ""

echo "3️⃣ Testing slash command through proxy..."
echo ""

# Test with a simple slash command
curl -X POST http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-key" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "/hello World"}
    ],
    "stream": false
  }' 2>/dev/null | python -m json.tool | head -30

echo ""
echo "4️⃣ Checking proxy logs..."
tail -20 proxy_test.log | grep -E "(Detected|Injected|Modified)"

echo ""
echo "5️⃣ Cleaning up..."
kill $PROXY_PID 2>/dev/null

echo ""
echo "✅ Test complete!"
echo ""
echo "💡 To use this mode with Codex CLI:"
echo "   export OPENAI_BASE_URL=http://localhost:3000"
echo "   export CODEX_PLUS_MIDDLEWARE=llm"
echo "   ./proxy.sh"
echo "   codex"
