# Circleback MCP Server

MCP Server (Model Context Protocol) multi-tenant que conecta Amazon QuickSight à API do [Circleback.ai](https://circleback.ai) via OAuth com PKCE.

Cada usuário faz login na sua própria conta Circleback — os tokens ficam isolados no DynamoDB.

## Arquitetura

```
QuickSight (usuário A) ─┐
QuickSight (usuário B) ─┤──→ Lambda (MCP Server) ──→ DynamoDB (tokens por user)
QuickSight (usuário C) ─┘         │
                                  ↓
                         Circleback API v2 (dados de cada conta)
```

## Ferramentas MCP Disponíveis

| Tool | Descrição |
|------|-----------|
| `search_meetings` | Pesquisa reuniões por palavra-chave, data, tags, participantes |
| `get_meeting_details` | Obtém detalhes completos de uma reunião específica |
| `search_transcripts` | Busca em transcrições de reuniões com timestamps |
| `search_action_items` | Encontra action items por palavra-chave, status ou assignee |
| `search_emails` | Pesquisa emails por palavra-chave, remetente ou destinatário |
| `find_profile` | Procura uma pessoa pelo nome e obtém seu perfil |

## Fluxo de Autenticação OAuth (PKCE)

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  QuickSight  │     │  Lambda (este)  │     │   Circleback     │
└──────┬───────┘     └────────┬────────┘     └────────┬─────────┘
       │                      │                       │
       │ 1. GET /oauth/authorize                      │
       │─────────────────────>│                       │
       │                      │ 2. Gera PKCE          │
       │                      │    code_verifier      │
       │                      │                       │
       │                      │ 3. Redirect com       │
       │                      │    code_challenge     │
       │<─────────────────────│──────────────────────>│
       │                      │                       │
       │                      │ 4. User autoriza      │
       │                      │<──────────────────────│
       │                      │    (callback + code)  │
       │                      │                       │
       │                      │ 5. Troca code com     │
       │                      │    code_verifier      │
       │                      │──────────────────────>│
       │                      │                       │
       │                      │ 6. Recebe tokens      │
       │                      │<──────────────────────│
       │                      │                       │
       │ 7. Redirect com code │                       │
       │<─────────────────────│                       │
       │                      │                       │
       │ 8. POST /oauth/token │                       │
       │─────────────────────>│                       │
       │                      │                       │
       │ 9. access_token      │                       │
       │<─────────────────────│                       │
       │                      │                       │
       │ 10. POST /mcp        │                       │
       │    (Bearer token)    │                       │
       │─────────────────────>│──────────────────────>│
       │                      │    API calls          │
```

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Health check |
| `GET` | `/oauth/authorize` | Inicia fluxo OAuth (QuickSight redireciona aqui) |
| `GET` | `/oauth/circleback-callback` | Callback do Circleback após autorização |
| `POST` | `/oauth/token` | Token exchange (QuickSight troca code por access_token) |
| `POST` | `/mcp` | Endpoint MCP Protocol (requer Bearer token) |

## Quick Start

### Pré-requisitos

- Node.js >= 18.x
- AWS CLI configurado com profile `dati-quick-labs`
- Conta no [Circleback Developer](https://circleback.ai/settings/developers)

### Instalação

```bash
# Clonar o repositório
git clone <repo-url>
cd circleback-mcp-server

# Instalar dependências
npm install

# Copiar e configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais
```

### Desenvolvimento Local

```bash
npm run dev
# Servidor rodando em http://localhost:3000
```

### Deploy (Serverless Framework)

```bash
npx serverless deploy --stage prod

# Output:
# endpoints:
#   ANY - https://xxxxxx.execute-api.us-east-1.amazonaws.com/prod/{proxy+}
```

### Deploy (AWS CDK)

```bash
cd infra
pip install -r requirements.txt
cdk deploy
```

## Configuração no QuickSight

1. Copie a URL base gerada no deploy
2. No QuickSight: **Settings → Capabilities → MCP**
3. **"+ Add MCP Server"** → **Remote HTTP**
4. Configure:
   - **MCP Endpoint**: `{base_url}/mcp`
   - **OAuth Authorization URL**: `{base_url}/oauth/authorize`
   - **OAuth Token URL**: `{base_url}/oauth/token`
   - **Client ID**: `circleback-quicksight-mcp`
   - **Client Secret**: `dati-qs-circleback-2024-secret`

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `CIRCLEBACK_CLIENT_ID` | Client ID OAuth do Circleback | — |
| `TOKEN_TABLE` | Nome da tabela DynamoDB | `circleback-mcp-tokens` |
| `API_BASE_URL` | URL base do API Gateway (auto) | — |
| `NODE_ENV` | Ambiente de execução | `production` |
| `PORT` | Porta para dev local | `3000` |
| `AWS_REGION` | Região AWS | `us-east-1` |

## Recursos AWS Criados

| Recurso | Nome | Descrição |
|---------|------|-----------|
| Lambda | `circleback-mcp-server` | Função principal (256MB, 30s timeout) |
| API Gateway | REST API | Proxy para Lambda com CORS |
| DynamoDB | `circleback-mcp-tokens` | Tokens OAuth por usuário (PAY_PER_REQUEST, TTL) |
| CloudWatch | Log Group | Retenção de 2 semanas |

## Estrutura do Projeto

```
circleback-mcp-server/
├── src/
│   ├── index.js              # Entry point, Express routes, Lambda handler
│   ├── mcp-server.js         # MCP protocol handler (JSON-RPC)
│   ├── tools.js              # Definição das 6 ferramentas MCP
│   ├── circleback-client.js  # HTTP client para Circleback API v2
│   ├── auth.js               # OAuth com PKCE (proxy para Circleback)
│   └── token-store.js        # DynamoDB wrapper para tokens
├── infra/
│   ├── app.py                # CDK app entry point
│   ├── stack.py              # Stack CDK (Lambda + API GW + DynamoDB)
│   └── requirements.txt      # Dependências Python do CDK
├── .env.example              # Template de variáveis de ambiente
├── package.json              # Dependências Node.js
├── serverless.yml            # Deploy via Serverless Framework
└── README.md                 # Esta documentação
```

## Tecnologias

- **Runtime**: Node.js 18.x
- **Framework**: Express + serverless-http
- **Protocolo**: MCP (Model Context Protocol) v2024-11-05
- **Auth**: OAuth 2.0 com PKCE (S256)
- **Storage**: DynamoDB (tokens)
- **Deploy**: Serverless Framework ou AWS CDK
- **API Client**: Axios

## Licença

Projeto interno - Dati Quick Labs
