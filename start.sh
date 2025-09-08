#!/bin/bash
# Codex-Plus Startup Script
# Starts both LiteLLM proxy and Node.js middleware

set -e

echo "🚀 Starting Codex-Plus Hybrid Architecture"

# Check if .env exists
if [[ ! -f .env ]]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env with your API keys before continuing"
    exit 1
fi

# Source environment variables
source .env

# API keys are optional when using Codex CLI forwarded headers
if [[ ! -z "$OPENAI_API_KEY" && "$OPENAI_API_KEY" != "your_openai_api_key_here" ]]; then
    echo "✅ OPENAI_API_KEY detected (direct API access enabled)"
else
    echo "ℹ️  Using Codex CLI forwarded authentication headers"
fi

echo "✅ Configuration loaded"

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down Codex-Plus..."
    if [[ ! -z "$LITELLM_PID" ]]; then
        kill $LITELLM_PID 2>/dev/null || true
        echo "   Stopped LiteLLM proxy"
    fi
    if [[ ! -z "$MIDDLEWARE_PID" ]]; then
        kill $MIDDLEWARE_PID 2>/dev/null || true  
        echo "   Stopped Node.js middleware"
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "🐍 Starting LiteLLM proxy on port $LITELLM_PORT..."
python litellm_proxy.py &
LITELLM_PID=$!

# Wait a moment for LiteLLM to start
sleep 3

# Check if LiteLLM is running
if ! curl -s http://localhost:$LITELLM_PORT/health > /dev/null; then
    echo "❌ LiteLLM proxy failed to start"
    cleanup
fi

echo "✅ LiteLLM proxy started (PID: $LITELLM_PID)"

echo "🟢 Starting Node.js middleware on port $PORT..."
node src/middleware.js &
MIDDLEWARE_PID=$!

# Wait a moment for middleware to start  
sleep 2

# Check if middleware is running
if ! curl -s http://localhost:$PORT/health > /dev/null; then
    echo "❌ Node.js middleware failed to start"
    cleanup
fi

echo "✅ Node.js middleware started (PID: $MIDDLEWARE_PID)"

echo ""
echo "🎉 Codex-Plus is running!"
echo ""
echo "   Middleware:  http://localhost:$PORT"
echo "   LiteLLM:     http://localhost:$LITELLM_PORT"
echo ""  
echo "🔧 Setup Codex CLI:"
echo "   export OPENAI_BASE_URL=http://localhost:$PORT"
echo "   codex \"Hello world\""
echo ""
echo "💡 Try slash commands:"
echo "   codex \"/help\""
echo "   codex \"/status\""
echo ""
echo "Press Ctrl+C to stop"

# Wait for background processes
wait