# 🔗 Circleback MCP Server - Deploy em Lambda + Quick

## 📋 Visão Geral

MCP Server Node.js que conecta à API do Circleback via OAuth e expõe ferramentas para:
- 🔍 Buscar reuniões
- 🎙️ Acessar transcrições
- 📧 Pesquisar emails
- ✅ Listar action items
- 👥 Encontrar perfis

**Hospedagem**: AWS Lambda (Serverless)  
**Consumidor**: Amazon Quick Web  
**Autenticação**: OAuth 2.0 (Circleback)

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────┐
│    Amazon Quick Web                     │
│  (Settings → MCP → Add Server)          │
└────────────────┬────────────────────────┘
                 │ HTTP/WebSocket
                 ↓
┌─────────────────────────────────────────┐
│  AWS Lambda (circleback-mcp-server)    │
│  - Node.js 18+                          │
│  - Express + MCP SDK                    │
│  - Gerencia OAuth & tokens              │
└────────────────┬────────────────────────┘
                 │ HTTPS
                 ↓
┌─────────────────────────────────────────┐
│  Circleback API                         │
│  (https://api.circleback.ai)            │
└─────────────────────────────────────────┘
```

---

## 📦 Estrutura do Projeto

```
circleback-mcp-server/
├── src/
│   ├── index.js              # Entry point Lambda
│   ├── mcp-server.js         # MCP Protocol Handler
│   ├── circleback-client.js  # API Client
│   ├── tools.js              # Tool Definitions
│   └── auth.js               # OAuth Handler
├── package.json
├── .env.example
├── README.md
└── serverless.yml            # (Opcional) Serverless Framework
```

---

## 📄 1. `package.json`

```json
{
  "name": "circleback-mcp-server",
  "version": "1.0.0",
  "description": "Circleback MCP Server for Amazon Quick",
  "main": "src/index.js",
  "type": "module",
  "scripts": {
    "start": "node src/index.js",
    "dev": "NODE_ENV=development node src/index.js",
    "test": "node --test tests/**/*.test.js",
    "deploy": "serverless deploy"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.4.0",
    "express": "^4.18.2",
    "axios": "^1.6.0",
    "dotenv": "^16.3.1",
    "jsonwebtoken": "^9.1.0",
    "uuid": "^9.0.1"
  },
  "devDependencies": {
    "serverless": "^3.38.0",
    "serverless-http": "^3.2.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

---

## 📄 2. `src/index.js` - Entry Point

```javascript
import express from 'express';
import { createServer } from 'http';
import { MCPServer } from './mcp-server.js';
import { CirclebackAuth } from './auth.js';

const app = express();
app.use(express.json());

const mcpServer = new MCPServer();
const auth = new CirclebackAuth();

// Health Check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// OAuth Callback Handler
app.get('/oauth/callback', async (req, res) => {
  try {
    const { code, state } = req.query;
    const tokens = await auth.exchangeCode(code, state);
    
    res.json({
      success: true,
      message: 'Autenticação concluída com sucesso!',
      tokens
    });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// MCP Protocol Endpoint (WebSocket ou HTTP Streaming)
app.post('/mcp', async (req, res) => {
  try {
    const request = req.body;
    const response = await mcpServer.handleRequest(request, auth);
    res.json(response);
  } catch (error) {
    console.error('MCP Error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Lambda Handler (para AWS Lambda + API Gateway)
export const handler = (event, context) => {
  return new Promise((resolve, reject) => {
    app(event, {}, (error, response) => {
      if (error) reject(error);
      else resolve(response);
    });
  });
};

// Local Development Server
if (process.env.NODE_ENV !== 'lambda') {
  const PORT = process.env.PORT || 3000;
  createServer(app).listen(PORT, () => {
    console.log(`🚀 Circleback MCP Server rodando em http://localhost:${PORT}`);
    console.log(`📋 Health Check: http://localhost:${PORT}/health`);
  });
}
```

---

## 📄 3. `src/mcp-server.js` - MCP Protocol Handler

```javascript
import { v4 as uuidv4 } from 'uuid';
import { tools } from './tools.js';
import { CirclebackClient } from './circleback-client.js';

export class MCPServer {
  constructor() {
    this.client = new CirclebackClient();
    this.tools = tools;
    this.activeTokens = new Map(); // Armazena tokens por sessão
  }

  async handleRequest(request, auth) {
    const { jsonrpc, method, params, id } = request;

    try {
      let result;

      switch (method) {
        case 'initialize':
          result = this.handleInitialize();
          break;

        case 'tools/list':
          result = this.handleListTools();
          break;

        case 'tools/call':
          result = await this.handleToolCall(params, auth);
          break;

        default:
          throw new Error(`Método desconhecido: ${method}`);
      }

      return {
        jsonrpc,
        result,
        id
      };
    } catch (error) {
      return {
        jsonrpc,
        error: {
          code: -32603,
          message: error.message
        },
        id
      };
    }
  }

  handleInitialize() {
    return {
      protocolVersion: '2024-11-05',
      capabilities: {
        tools: {}
      },
      serverInfo: {
        name: 'Circleback MCP Server',
        version: '1.0.0'
      }
    };
  }

  handleListTools() {
    return {
      tools: this.tools.map(tool => ({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.inputSchema
      }))
    };
  }

  async handleToolCall(params, auth) {
    const { name, arguments: args } = params;
    const tool = this.tools.find(t => t.name === name);

    if (!tool) {
      throw new Error(`Ferramenta não encontrada: ${name}`);
    }

    // Obter token válido
    const token = await auth.getValidToken();
    this.client.setToken(token);

    // Executar ferramenta
    return await tool.handler(args, this.client);
  }
}
```

---

## 📄 4. `src/circleback-client.js` - API Client

```javascript
import axios from 'axios';

export class CirclebackClient {
  constructor() {
    this.baseURL = 'https://api.circleback.ai/v2';
    this.token = null;
  }

  setToken(token) {
    this.token = token;
  }

  async request(method, endpoint, data = null) {
    try {
      const config = {
        method,
        url: `${this.baseURL}${endpoint}`,
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
          'User-Agent': 'Circleback-MCP-Server/1.0'
        }
      };

      if (data) {
        config.data = data;
      }

      const response = await axios(config);
      return response.data;
    } catch (error) {
      throw new Error(
        `Circleback API Error: ${error.response?.status} - ${error.response?.data?.message || error.message}`
      );
    }
  }

  // ========== MEETINGS ==========
  async searchMeetings(query, options = {}) {
    const params = new URLSearchParams({
      q: query,
      limit: options.limit || 10,
      offset: options.offset || 0,
      ...(options.tag && { tag: options.tag }),
      ...(options.attendee && { attendee: options.attendee }),
      ...(options.startDate && { startDate: options.startDate }),
      ...(options.endDate && { endDate: options.endDate })
    });

    return this.request('GET', `/meetings/search?${params}`);
  }

  async getMeeting(meetingId) {
    return this.request('GET', `/meetings/${meetingId}`);
  }

  async listMeetings(options = {}) {
    const params = new URLSearchParams({
      limit: options.limit || 20,
      offset: options.offset || 0
    });
    return this.request('GET', `/meetings?${params}`);
  }

  // ========== TRANSCRIPTS ==========
  async searchTranscripts(query, options = {}) {
    return this.request('POST', '/transcripts/search', {
      query,
      limit: options.limit || 10,
      meetingId: options.meetingId
    });
  }

  async getTranscript(meetingId) {
    return this.request('GET', `/meetings/${meetingId}/transcript`);
  }

  // ========== ACTION ITEMS ==========
  async searchActionItems(query, options = {}) {
    const params = new URLSearchParams({
      q: query,
      status: options.status || 'all', // 'pending', 'done', 'all'
      limit: options.limit || 10
    });
    return this.request('GET', `/action-items/search?${params}`);
  }

  async getActionItem(itemId) {
    return this.request('GET', `/action-items/${itemId}`);
  }

  // ========== EMAILS ==========
  async searchEmails(query, options = {}) {
    return this.request('POST', '/emails/search', {
      query,
      sender: options.sender,
      recipient: options.recipient,
      limit: options.limit || 10
    });
  }

  // ========== PROFILES ==========
  async findProfile(name) {
    const params = new URLSearchParams({ name });
    return this.request('GET', `/profiles/search?${params}`);
  }

  async getProfile(profileId) {
    return this.request('GET', `/profiles/${profileId}`);
  }

  // ========== CALENDAR ==========
  async searchCalendarEvents(options = {}) {
    const params = new URLSearchParams({
      limit: options.limit || 10,
      ...(options.startDate && { startDate: options.startDate }),
      ...(options.endDate && { endDate: options.endDate })
    });
    return this.request('GET', `/calendar/events?${params}`);
  }
}
```

---

## 📄 5. `src/tools.js` - Tool Definitions

```javascript
export const tools = [
  {
    name: 'search_meetings',
    description: 'Pesquisa reuniões por palavra-chave, data, tags, participantes',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave ou assunto da reunião'
        },
        tag: {
          type: 'string',
          description: 'Filtrar por tag específica (opcional)'
        },
        attendee: {
          type: 'string',
          description: 'Filtrar por participante (opcional)'
        },
        startDate: {
          type: 'string',
          description: 'Data inicial (YYYY-MM-DD) (opcional)'
        },
        endDate: {
          type: 'string',
          description: 'Data final (YYYY-MM-DD) (opcional)'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados (padrão: 10)'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchMeetings(args.query, {
        tag: args.tag,
        attendee: args.attendee,
        startDate: args.startDate,
        endDate: args.endDate,
        limit: args.limit
      });
    }
  },

  {
    name: 'get_meeting_details',
    description: 'Obtém detalhes completos de uma reunião específica',
    inputSchema: {
      type: 'object',
      properties: {
        meetingId: {
          type: 'string',
          description: 'ID da reunião'
        }
      },
      required: ['meetingId']
    },
    handler: async (args, client) => {
      return client.getMeeting(args.meetingId);
    }
  },

  {
    name: 'search_transcripts',
    description: 'Busca em transcrições de reuniões com timestamps',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave para buscar nas transcrições'
        },
        meetingId: {
          type: 'string',
          description: 'ID da reunião específica (opcional)'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchTranscripts(args.query, {
        meetingId: args.meetingId,
        limit: args.limit
      });
    }
  },

  {
    name: 'search_action_items',
    description: 'Encontra action items por palavra-chave, status ou assignee',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave para buscar'
        },
        status: {
          type: 'string',
          enum: ['pending', 'done', 'all'],
          description: 'Filtrar por status'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchActionItems(args.query, {
        status: args.status,
        limit: args.limit
      });
    }
  },

  {
    name: 'search_emails',
    description: 'Pesquisa emails por palavra-chave, remetente ou destinatário',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave'
        },
        sender: {
          type: 'string',
          description: 'Email do remetente (opcional)'
        },
        recipient: {
          type: 'string',
          description: 'Email do destinatário (opcional)'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchEmails(args.query, {
        sender: args.sender,
        recipient: args.recipient,
        limit: args.limit
      });
    }
  },

  {
    name: 'find_profile',
    description: 'Procura uma pessoa pelo nome e obtém seu perfil',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Nome da pessoa'
        }
      },
      required: ['name']
    },
    handler: async (args, client) => {
      return client.findProfile(args.name);
    }
  }
];
```

---

## 📄 6. `src/auth.js` - OAuth Handler

```javascript
import axios from 'axios';
import jwt from 'jsonwebtoken';

export class CirclebackAuth {
  constructor() {
    this.clientId = process.env.CIRCLEBACK_CLIENT_ID;
    this.clientSecret = process.env.CIRCLEBACK_CLIENT_SECRET;
    this.redirectUri = process.env.CIRCLEBACK_REDIRECT_URI || 
      'https://us-east-1.quicklight.amazon.com/oauth/callback';
    
    this.tokenCache = new Map();
    this.baseURL = 'https://api.circleback.ai';
  }

  getAuthorizationUrl(state) {
    const params = new URLSearchParams({
      client_id: this.clientId,
      response_type: 'code',
      redirect_uri: this.redirectUri,
      state,
      scope: 'read:meetings read:transcripts read:emails read:calendar'
    });

    return `${this.baseURL}/oauth/authorize?${params}`;
  }

  async exchangeCode(code, state) {
    try {
      const response = await axios.post(
        `${this.baseURL}/oauth/token`,
        {
          grant_type: 'authorization_code',
          code,
          client_id: this.clientId,
          client_secret: this.clientSecret,
          redirect_uri: this.redirectUri
        }
      );

      const { access_token, refresh_token, expires_in } = response.data;

      // Armazenar tokens
      const tokenData = {
        accessToken: access_token,
        refreshToken: refresh_token,
        expiresAt: Date.now() + expires_in * 1000
      };

      this.tokenCache.set(state, tokenData);

      return tokenData;
    } catch (error) {
      throw new Error(
        `Falha na autenticação OAuth: ${error.response?.data?.error_description || error.message}`
      );
    }
  }

  async refreshAccessToken(refreshToken) {
    try {
      const response = await axios.post(
        `${this.baseURL}/oauth/token`,
        {
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: this.clientId,
          client_secret: this.clientSecret
        }
      );

      const { access_token, refresh_token, expires_in } = response.data;

      return {
        accessToken: access_token,
        refreshToken: refresh_token,
        expiresAt: Date.now() + expires_in * 1000
      };
    } catch (error) {
      throw new Error('Falha ao renovar token');
    }
  }

  async getValidToken() {
    // Lógica para obter um token válido (do cache ou renovar se necessário)
    // Em produção, você pode consultar um banco de dados ou cache distribuído (Redis)
    
    if (this.tokenCache.size === 0) {
      throw new Error('Nenhum token disponível. Execute a autenticação primeiro.');
    }

    const tokenData = this.tokenCache.values().next().value;

    // Se token expirou, renovar
    if (Date.now() > tokenData.expiresAt) {
      const newToken = await this.refreshAccessToken(tokenData.refreshToken);
      return newToken.accessToken;
    }

    return tokenData.accessToken;
  }
}
```

---

## 📄 7. `.env.example`

```bash
# Circleback OAuth
CIRCLEBACK_CLIENT_ID=seu_client_id_aqui
CIRCLEBACK_CLIENT_SECRET=seu_client_secret_aqui
CIRCLEBACK_REDIRECT_URI=https://us-east-1.quicklight.amazon.com/oauth/callback

# Environment
NODE_ENV=production
PORT=3000

# AWS Lambda
AWS_LAMBDA_FUNCTION_NAME=circleback-mcp-server
AWS_REGION=us-east-1
```

---

## 📄 8. `serverless.yml` - Deploy em Lambda

```yaml
service: circleback-mcp-server

provider:
  name: aws
  runtime: nodejs18.x
  region: us-east-1
  environment:
    CIRCLEBACK_CLIENT_ID: ${env:CIRCLEBACK_CLIENT_ID}
    CIRCLEBACK_CLIENT_SECRET: ${env:CIRCLEBACK_CLIENT_SECRET}
    CIRCLEBACK_REDIRECT_URI: ${env:CIRCLEBACK_REDIRECT_URI}
    NODE_ENV: production

functions:
  api:
    handler: src/index.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
          cors: true
      - http:
          path: /
          method: ANY
          cors: true

plugins:
  - serverless-http

package:
  individually: true
  patterns:
    - '!node_modules/**'
    - '!.git/**'
    - 'src/**'
    - 'package.json'
```

---

## 🚀 Deploy & Setup

### 1. **Preparar o Projeto**

```bash
# Clone ou crie a pasta
mkdir circleback-mcp-server && cd circleback-mcp-server

# Copie os arquivos acima

# Instale dependências
npm install

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais Circleback
```

### 2. **Testar Localmente**

```bash
npm run dev
# Acesse: http://localhost:3000/health
```

### 3. **Deploy em Lambda**

```bash
# Instale Serverless Framework
npm install -g serverless

# Configure AWS credentials
aws configure

# Deploy
npm run deploy

# Saída esperada:
# ✔ Service deployed to stack circleback-mcp-server-dev
# ✔ Endpoint: https://xxxxxx.lambda-url.us-east-1.on.aws
```

### 4. **Conectar no Amazon Quick Web**

1. Copie a URL do Lambda (ex: `https://xxxxxx.lambda-url.us-east-1.on.aws`)
2. No Quick Web, vá em **Settings → Capabilities → MCP**
3. Clique em **"+ Add MCP Server"**
4. Escolha **"Remote HTTP"**
5. Cole a URL do Lambda
6. Clique em **"Connect"**
7. Você será redirecionado para autenticar no Circleback
8. Autorize o acesso
9. ✅ Integração ativa!

---

## ✅ Checklist de Deploy

- [ ] Node.js 18+ instalado
- [ ] npm dependências instaladas
- [ ] Variáveis `.env` configuradas
- [ ] Lambda deployado com sucesso
- [ ] URL do Lambda obtida
- [ ] Quick Web conectado ao MCP
- [ ] Autenticação Circleback concluída
- [ ] Testes com `search_meetings` funcionando

---

## 📞 Troubleshooting

### "Lambda retorna 502 Bad Gateway"
- Verifique se as variáveis de ambiente estão definidas
- Confira os logs: `serverless logs -f api`

### "Erro de autenticação OAuth"
- Valide `CIRCLEBACK_CLIENT_ID` e `CIRCLEBACK_CLIENT_SECRET`
- Confirme que `CIRCLEBACK_REDIRECT_URI` é exatamente o mesmo no Circleback

### "Ferramenta não encontrada"
- Verifique se o token está válido
- Confira se a conta Circleback tem acesso aos dados

---

## 📚 Referências

- [Circleback API Docs](https://circleback.ai/docs/api)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [AWS Lambda Node.js](https://docs.aws.amazon.com/lambda/latest/dg/nodejs-handler.html)
- [Serverless Framework](https://www.serverless.com/framework/docs)

