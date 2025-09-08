#!/usr/bin/env node
/**
 * Codex-Plus Middleware Server
 * Node.js proxy that handles slash commands, hooks, and MCP integration
 * Forwards processed requests to LiteLLM proxy for multi-provider routing
 */

const express = require('express');
const axios = require('axios');
const { createProxyMiddleware } = require('http-proxy-middleware');
const fs = require('fs');
const path = require('path');
const os = require('os');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;
const LITELLM_URL = process.env.LITELLM_URL || 'http://localhost:4000';

// Load codex auth if available
let codexAuth = null;
const authPath = path.join(os.homedir(), '.codex', 'auth.json');
if (fs.existsSync(authPath)) {
  try {
    const authData = JSON.parse(fs.readFileSync(authPath, 'utf8'));
    if (authData.tokens && authData.tokens.access_token) {
      codexAuth = authData.tokens.access_token;
      console.log('✅ Loaded Codex auth token');
    }
  } catch (error) {
    console.error('Failed to load Codex auth:', error.message);
  }
}

// Middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.raw({ type: 'application/octet-stream', limit: '10mb' }));

// Enable CORS for development
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  if (req.method === 'OPTIONS') {
    res.sendStatus(200);
  } else {
    next();
  }
});

// Logging middleware
app.use((req, res, next) => {
  const start = Date.now();
  const clientIP = req.ip || req.connection.remoteAddress || 'unknown';
  
  res.on('finish', () => {
    const duration = Date.now() - start;
    const outcome = res.statusCode >= 400 ? 'FAIL' : 'OK';
    console.log(`${outcome} ${req.method} ${req.path} -> ${res.statusCode} (${duration}ms, ip=${clientIP})`);
  });
  
  next();
});

// Health check endpoint
app.get('/health', async (req, res) => {
  try {
    // Check LiteLLM health
    const litellmHealth = await axios.get(`${LITELLM_URL}/health`, { timeout: 5000 });
    
    res.json({
      status: 'healthy',
      message: 'Codex Plus, all systems operational',
      timestamp: new Date().toISOString(),
      components: {
        middleware: 'healthy',
        litellm: litellmHealth.status === 200 ? 'healthy' : 'unhealthy'
      },
      version: '2.0.0'
    });
  } catch (error) {
    res.status(503).json({
      status: 'degraded',
      message: 'Codex Plus, system partially degraded',
      timestamp: new Date().toISOString(),
      components: {
        middleware: 'healthy',
        litellm: 'unhealthy'
      },
      error: error.message
    });
  }
});

// Slash command detection and processing
function isSlashCommand(content) {
  if (typeof content !== 'string') return false;
  return content.trim().startsWith('/') && content.trim().split(' ')[0].length > 1;
}

async function processSlashCommand(command) {
  console.log(`Processing slash command: ${command}`);
  
  // Basic built-in commands
  if (command === '/help') {
    return {
      role: 'assistant',
      content: `Codex Plus, here are the available commands:

# Codex-Plus Commands

## Built-in Commands
- \`/help\` - Show this help message
- \`/status\` - Show system status  
- \`/health\` - Check system health

## System Info
- Middleware: Running on port ${PORT}
- LiteLLM: Running on ${LITELLM_URL}
- Version: 2.0.0

More commands can be added in \`.claude/commands/\` directory.`
    };
  }
  
  if (command === '/status') {
    try {
      const litellmHealth = await axios.get(`${LITELLM_URL}/health`, { timeout: 3000 });
      return {
        role: 'assistant',
        content: `Codex Plus, system status report:

# System Status

✅ **Middleware**: Healthy (port ${PORT})
✅ **LiteLLM Proxy**: Healthy (${LITELLM_URL})
🔄 **Configuration**: .claude/.codex fallback system active

Ready to process requests!`
      };
    } catch (error) {
      return {
        role: 'assistant', 
        content: `Codex Plus, system status report:

# System Status

✅ **Middleware**: Healthy (port ${PORT})
❌ **LiteLLM Proxy**: Unavailable (${LITELLM_URL})
⚠️  **Status**: Degraded - LiteLLM connection failed

Error: ${error.message}`
      };
    }
  }
  
  // Default response for unknown commands
  return {
    role: 'assistant',
    content: `Codex Plus, unknown command: ${command}

Use \`/help\` to see available commands.`
  };
}

// Main request handler for chat completions
app.post('/v1/chat/completions', async (req, res) => {
  try {
    let { messages, model, stream, ...otherParams } = req.body;
    
    // Check if the last message contains a slash command
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.role === 'user' && isSlashCommand(lastMessage.content)) {
      const commandResponse = await processSlashCommand(lastMessage.content.trim());
      
      // Return slash command response directly
      if (stream) {
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive'
        });
        
        const streamId = `chatcmpl-${Date.now()}`;
        const created = Math.floor(Date.now() / 1000);
        
        // First chunk with content
        const contentChunk = {
          id: streamId,
          object: 'chat.completion.chunk',
          created: created,
          model: model || 'codex-plus',
          choices: [{
            index: 0,
            delta: { content: commandResponse.content },
            finish_reason: null
          }]
        };
        
        // Final chunk with finish_reason
        const finishChunk = {
          id: streamId,
          object: 'chat.completion.chunk',
          created: created,
          model: model || 'codex-plus',
          choices: [{
            index: 0,
            delta: {},
            finish_reason: 'stop'
          }]
        };
        
        res.write(`data: ${JSON.stringify(contentChunk)}\n\n`);
        res.write(`data: ${JSON.stringify(finishChunk)}\n\n`);
        res.write('data: [DONE]\n\n');
        res.end();
      } else {
        res.json({
          id: `chatcmpl-${Date.now()}`,
          object: 'chat.completion',
          created: Math.floor(Date.now() / 1000),
          model: model || 'codex-plus',
          choices: [{
            index: 0,
            message: commandResponse,
            finish_reason: 'stop'
          }],
          usage: {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0
          }
        });
      }
      return;
    }
    
    // Forward non-slash requests to LiteLLM with preserved headers
    // Use auth from request header, or fall back to codex auth token
    const authHeader = req.headers.authorization || (codexAuth ? `Bearer ${codexAuth}` : null);
    
    const forwardHeaders = {
      'Content-Type': 'application/json',
      // Include authentication header
      ...(authHeader && { 'Authorization': authHeader }),
      // Remove hop-by-hop headers
      ...(req.headers['user-agent'] && { 'User-Agent': req.headers['user-agent'] }),
      ...(req.headers['accept'] && { 'Accept': req.headers['accept'] }),
    };
    
    console.log(`Forwarding to LiteLLM: ${req.method} /v1/chat/completions (auth: ${authHeader ? 'injected' : 'none'})`);
    
    const response = await axios({
      method: 'POST',
      url: `${LITELLM_URL}/v1/chat/completions`,
      data: req.body,
      headers: forwardHeaders,
      responseType: stream ? 'stream' : 'json',
      timeout: 300000 // 5 minute timeout
    });
    
    if (stream) {
      // Stream response from LiteLLM
      res.writeHead(response.status, response.headers);
      response.data.pipe(res);
    } else {
      // Regular JSON response
      res.status(response.status).json(response.data);
    }
    
  } catch (error) {
    console.error('Request processing error:', error.message);
    
    if (error.response && error.response.data) {
      // Forward error from LiteLLM, safely handle potential circular references
      try {
        res.status(error.response.status).json(error.response.data);
      } catch (jsonError) {
        console.error('JSON serialization error:', jsonError.message);
        res.status(error.response.status).json({
          error: {
            message: error.response.statusText || 'LiteLLM proxy error',
            type: 'proxy_error',
            code: 'litellm_error'
          }
        });
      }
    } else {
      // Internal middleware error
      res.status(500).json({
        error: {
          message: 'Internal proxy error',
          type: 'proxy_error',
          code: 'internal_error'
        }
      });
    }
  }
});

// Proxy all other requests to LiteLLM
app.use('/', createProxyMiddleware({
  target: LITELLM_URL,
  changeOrigin: true,
  onError: (err, req, res) => {
    console.error('Proxy error:', err.message);
    res.status(503).json({
      error: {
        message: 'LiteLLM proxy unavailable',
        type: 'proxy_error',
        code: 'service_unavailable'
      }
    });
  }
}));

// Start server
app.listen(PORT, '127.0.0.1', () => {
  console.log(`
🚀 Codex Plus Middleware Server Started

   Port: ${PORT}
   LiteLLM: ${LITELLM_URL}
   Health: http://localhost:${PORT}/health

🔧 Next Steps:
   1. Start LiteLLM: npm run litellm
   2. Test: export OPENAI_BASE_URL=http://localhost:${PORT}
   3. Use: codex "Hello world"

✨ Codex Plus ready for integration!
`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('Received SIGINT, shutting down gracefully');
  process.exit(0);
});