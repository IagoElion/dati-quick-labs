# Dati Quick Labs — MCP Servers

Coleção de MCP Servers (Model Context Protocol) desenvolvidos pela Dati para integrar sistemas externos ao Amazon QuickSight (Amazon Q).

## Visão Geral

| MCP Server | Sistema | Auth | Runtime | Tools | Status |
|------------|---------|------|---------|-------|--------|
| [mcp-piperun-white](#mcp-piperun-white) | PipeRun CRM | OAuth client_credentials | Python Lambda | 27 (R+W) | ✅ Produção |
| [mcp-piperun-oauth](#mcp-piperun-oauth) | PipeRun CRM | OAuth + Login Page | Python Lambda | 19 (R) | ✅ Produção |
| [mcp-piperun-cognito](#mcp-piperun-cognito) | PipeRun CRM | Cognito + PKCE | Python Lambda | 14 (R+W) | ✅ Produção |
| [mcp-tiflux](#mcp-tiflux) | Tiflux Helpdesk | OAuth client_credentials | Python Lambda | 6 (R) | ✅ Produção |
| [tiflux-mcp-server](#tiflux-mcp-server) | Tiflux Helpdesk | Bearer Token (local) | Node.js stdio | 9 (R+W) | ✅ Produção |
| [mcp-taggui](#mcp-taggui) | TagguiRH | OAuth + Login Page | Python Lambda | 7 (R+W) | ✅ Produção |
| [circleback-mcp-server](#circleback-mcp-server) | Circleback.ai | OAuth PKCE | Node.js Lambda | 6 (R) | ✅ Produção |
| [mcp-APN](#mcp-apn) | AWS Partner Central | IAM SigV4 (cross-account) | Managed AWS | 2 | 🔧 Config |
| [factorial-mcp-server](#factorial-mcp-server) | Factorial HR | OAuth2 | Java (Docker) | 11 (R+W) | 📦 Fork |

---

## mcp-piperun-white

MCP Server white-label para PipeRun CRM com **leitura e escrita** (27 tools). Usa OAuth `client_credentials` com token único armazenado no Secrets Manager.

- **Stack**: Python 3.13 + Lambda + Function URL + Secrets Manager
- **IaC**: AWS CDK (Python)
- **Auth**: Service-to-service (client_credentials)
- **API**: PipeRun v1 (`api.pipe.run/v1`)

### Tools de Leitura (19)
`list_opportunities` · `get_opportunity` · `list_companies` · `get_company` · `list_persons` · `get_person` · `list_pipelines` · `get_pipeline` · `list_stages` · `list_activities` · `list_proposals` · `get_proposal` · `list_notes` · `list_users` · `list_teams` · `list_tags` · `list_sources` · `list_items` · `list_custom_fields`

### Tools de Escrita (8)
`create_opportunity` · `update_opportunity` · `create_company` · `update_company` · `create_person` · `update_person` · `create_activity` · `create_note`

---

## mcp-piperun-oauth

MCP Server para PipeRun com autenticação individual por usuário. Cada usuário insere seu próprio token PipeRun via página de login no browser.

- **Stack**: Python 3.13 + Lambda + Function URL + DynamoDB
- **IaC**: AWS CDK (Python)
- **Auth**: OAuth Authorization Code (login page → token PipeRun)
- **Multi-tenant**: Sim (token por usuário no DynamoDB)
- **Tools**: 19 (read-only)

---

## mcp-piperun-cognito

MCP Server para PipeRun com autenticação via AWS Cognito (Google Workspace / email+senha). Arquitetura de 5 camadas com tokens individuais no Secrets Manager.

- **Stack**: Python 3.13 + Lambda + API Gateway HTTP + Cognito + Secrets Manager
- **IaC**: AWS CDK (TypeScript)
- **Auth**: Cognito OAuth 2.0 (Authorization Code + PKCE)
- **Multi-tenant**: Sim (token por `cognito_sub`)
- **Tools**: 14 (leitura + escrita)

### Tools de Leitura (7)
`piperun_listar_funis` · `piperun_listar_deals` · `piperun_obter_deal` · `piperun_buscar_contatos` · `piperun_obter_contato` · `piperun_listar_atividades` · `piperun_listar_propostas`

### Tools de Escrita (7)
`piperun_criar_deal` · `piperun_atualizar_deal` · `piperun_mover_etapa` · `piperun_criar_atividade` · `piperun_concluir_atividade` · `piperun_criar_nota` · `piperun_criar_proposta`

---

## mcp-tiflux

MCP Server read-only para Tiflux Helpdesk deployado como Lambda com Function URL. Auth via `client_credentials` com token armazenado no Secrets Manager.

- **Stack**: Python 3.13 + Lambda + Function URL + Secrets Manager
- **IaC**: AWS CDK (Python)
- **Auth**: OAuth client_credentials
- **API**: Tiflux v2 (`api.tiflux.com/api/v2`)

### Tools (6)
`list_tickets` · `get_ticket` · `list_clients` · `get_client` · `list_desks` · `get_ticket_appointments`

---

## tiflux-mcp-server

MCP Server local (stdio) para Tiflux. Roda direto na máquina do usuário — ideal para uso com Claude Desktop, Gemini CLI ou Amazon Q Developer.

- **Stack**: Node.js 18+ (MCP SDK)
- **Transport**: stdio (local)
- **Auth**: Bearer token direto (variável de ambiente)
- **API**: Tiflux v2

### Tools (9)
`list_tickets` · `get_ticket` · `create_ticket` · `update_ticket` · `close_ticket` · `list_clients` · `get_client` · `list_desks` · `add_communication`

---

## mcp-taggui

MCP Server para TagguiRH (sistema de RH). Usuário autentica com seu token de API do TagguiRH via página de login.

- **Stack**: Python 3.13 + Lambda + Function URL + DynamoDB
- **IaC**: AWS CDK (Python)
- **Auth**: OAuth + Login Page (token TagguiRH)
- **API**: TagguiRH v1 (`api.tagguirh.com.br/v1`)

### Tools (7)
`list_colaboradores` · `create_colaborador` · `update_colaborador` · `list_cargos` · `list_departamentos` · `list_equipes_ponto` · `list_batidas_ponto`

---

## circleback-mcp-server

MCP Server para Circleback.ai (meetings AI). Conecta QuickSight ao Circleback via OAuth com PKCE para acesso a reuniões, transcrições e action items.

- **Stack**: Node.js 18 + Express + Lambda + API Gateway + DynamoDB
- **IaC**: AWS CDK (Python) ou Serverless Framework
- **Auth**: OAuth 2.0 com PKCE (S256)
- **API**: Circleback v2 (`api.circleback.ai/v2`)

### Tools (6)
`search_meetings` · `get_meeting_details` · `search_transcripts` · `search_action_items` · `search_emails` · `find_profile`

---

## mcp-APN

Configuração do MCP Server gerenciado pela AWS para **AWS Partner Central Agents**. Não é código deployado — é integração cross-account via IAM SigV4.

- **Endpoint**: `https://partnercentral-agents-mcp.us-east-1.api.aws/mcp`
- **Auth**: SigV4 (cross-account: 601804669442 → 107028717321)
- **Managed by**: AWS (Bedrock AgentCore)
- **Custo**: $0 (incluso no Partner program)

### Tools (2)
`sendMessage` · `getSession`

### Capacidades
- Pipeline & Opportunity Insights
- Deal Progression
- Funding Programs (MAP, POC, WMP)
- Customer Insights

---

## factorial-mcp-server

Fork do [ratek-20/factorial-mcp-server](https://github.com/ratek-20/factorial-mcp-server). MCP Server para Factorial HR (gestão de férias e time-off).

- **Stack**: Java 25 + Spring Boot + Spring AI
- **Transport**: stdio (Docker)
- **Auth**: OAuth2 (Factorial)
- **Tools**: 11 (time-off management)

---

## Arquitetura Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                    Amazon QuickSight (Amazon Q)                  │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ├── OAuth/PKCE ──→ circleback-mcp-server (Lambda)
              ├── client_credentials ──→ mcp-piperun-white (Lambda)
              ├── Cognito PKCE ──→ mcp-piperun-cognito (Lambda)
              ├── OAuth + Login ──→ mcp-piperun-oauth (Lambda)
              ├── client_credentials ──→ mcp-tiflux (Lambda)
              ├── OAuth + Login ──→ mcp-taggui (Lambda)
              ├── IAM SigV4 ──→ AWS Partner Central (Managed)
              └── stdio ──→ tiflux-mcp-server (Local)
                           factorial-mcp-server (Docker)
```

## Deploy

Cada MCP tem seu próprio deploy. Ver README individual de cada pasta para instruções.

Padrão geral:
```bash
cd <mcp-folder>/cdk
pip install -r requirements.txt
cdk deploy --profile dati-quick-labs
```

## Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Compute | AWS Lambda (Python 3.13 / Node.js 18) |
| API | Lambda Function URL / API Gateway |
| Auth | OAuth 2.0, Cognito, IAM SigV4, PKCE |
| Storage | DynamoDB, Secrets Manager |
| IaC | AWS CDK (Python/TypeScript), Serverless Framework |
| Protocolo | MCP (JSON-RPC 2.0) v2024-11-05 |
| Observabilidade | CloudWatch, X-Ray, Lambda Powertools |

## Licença

Projeto interno — Dati Quick Labs
