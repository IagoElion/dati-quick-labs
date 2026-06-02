# Guia de Desenvolvimento - Circleback MCP Server

## Setup Local

### 1. Instalar dependências

```bash
npm install
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Editar `.env`:

```env
CIRCLEBACK_CLIENT_ID=seu_client_id
NODE_ENV=development
PORT=3000
TOKEN_TABLE=circleback-mcp-tokens
AWS_REGION=us-east-1
```

### 3. Rodar localmente

```bash
npm run dev
```

O servidor sobe em `http://localhost:3000`.

### 4. Testar health check

```bash
curl http://localhost:3000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "version": "2.0.0",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

## Estrutura do Código

### src/index.js

Entry point da aplicação. Configura Express, define rotas HTTP e exporta o handler Lambda via `serverless-http`.

- Rotas OAuth (authorize, callback, token)
- Rota MCP (POST /mcp)
- Health check
- Suporte a dev local com `createServer`

### src/mcp-server.js

Handler do protocolo MCP. Recebe requests JSON-RPC e despacha para o método correto:

- `initialize` → retorna capabilities e versão
- `tools/list` → retorna lista de ferramentas
- `tools/call` → executa ferramenta com token do usuário

### src/tools.js

Array com definição das 6 ferramentas MCP. Cada tool contém:

- `name` — identificador único
- `description` — descrição em português
- `inputSchema` — JSON Schema dos parâmetros
- `handler` — função async que executa a chamada

### src/circleback-client.js

Client HTTP para a API do Circleback v2 (`https://api.circleback.ai/v2`). Métodos:

- `searchMeetings(query, options)`
- `getMeeting(meetingId)`
- `listMeetings(options)`
- `searchTranscripts(query, options)`
- `getTranscript(meetingId)`
- `searchActionItems(query, options)`
- `getActionItem(itemId)`
- `searchEmails(query, options)`
- `findProfile(name)`
- `getProfile(profileId)`
- `searchCalendarEvents(options)`

### src/auth.js

Implementa OAuth com PKCE. Atua como Authorization Server intermediário:

- `handleAuthorize(redirectUri, state)` — gera PKCE e redireciona
- `handleCirclebackCallback(code, state)` — troca code e redireciona para QS
- `handleTokenExchange(grantType, code, refreshToken)` — token endpoint
- `ensureCirclebackClient()` — Dynamic Client Registration
- `validateQuickSightCredentials(clientId, clientSecret)` — validação

### src/token-store.js

Wrapper para DynamoDB. Operações:

- `saveTokens(userId, tokenData)` — salva access/refresh token
- `getTokens(userId)` — recupera tokens
- `deleteTokens(userId)` — remove tokens (logout)
- `saveOAuthState(state, userId)` — salva state temporário (TTL 10 min)
- `getUserIdByState(state)` — recupera userId por state

## Testando Requests MCP

### Listar ferramentas

```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
  }'
```

### Chamar uma ferramenta

```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_meetings",
      "arguments": { "query": "sprint" }
    },
    "id": 2
  }'
```

## Adicionando Novas Ferramentas

1. Adicionar método no `src/circleback-client.js`:

```javascript
async myNewMethod(params) {
  return this.request('GET', `/new-endpoint?param=${params.value}`);
}
```

2. Adicionar tool em `src/tools.js`:

```javascript
{
  name: 'my_new_tool',
  description: 'Descrição da nova ferramenta',
  inputSchema: {
    type: 'object',
    properties: {
      param: {
        type: 'string',
        description: 'Descrição do parâmetro'
      }
    },
    required: ['param']
  },
  handler: async (args, client) => {
    return client.myNewMethod(args);
  }
}
```

3. Deploy:

```bash
npx serverless deploy --stage prod
```

## Logs e Debug

### CloudWatch (produção)

```bash
# Ver logs em tempo real
aws logs tail /aws/lambda/circleback-mcp-server --follow --profile dati-quick-labs

# Últimos 5 minutos
aws logs tail /aws/lambda/circleback-mcp-server --since 5m --profile dati-quick-labs
```

### Local (desenvolvimento)

Os logs aparecem direto no terminal com `npm run dev`.

## Troubleshooting

| Erro | Causa | Solução |
|------|-------|---------|
| `Token de acesso obrigatório` | Request MCP sem Bearer token | Completar fluxo OAuth primeiro |
| `client_id inválido` | QuickSight com client_id errado | Verificar configuração no QS |
| `State inválido ou expirado` | OAuth state expirou (>10 min) | Reiniciar fluxo de autorização |
| `Circleback API Error: 401` | Token expirado | QuickSight deve fazer refresh |
| `grant_type não suportado` | Tipo de grant inválido | Usar `authorization_code` ou `refresh_token` |
