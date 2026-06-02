# MCP PipeRun com Cognito (Arquitetura 5 Camadas)

MCP Server para o PipeRun CRM com autenticação individual via AWS Cognito.
Cada usuário autentica com OAuth 2.0 (Authorization Code + PKCE) e seu token PipeRun
é armazenado no Secrets Manager indexado pelo `cognito_sub`.

## Arquitetura

```
┌──────────────┐     ┌─────────────────────────────────────┐     ┌─────────────┐
│  Amazon Quick│────▶│  API Gateway HTTP API                │────▶│ PipeRun API │
│  (Web/Desktop)     │                                     │     │ api.pipe.run│
└──────────────┘     │  /.well-known/* → OAuth metadata    │     └─────────────┘
       │             │  /mcp (POST)    → MCP Server Lambda │
       │             │  /register-token → Cadastro token   │
       ▼             └─────────────────────────────────────┘
  ┌─────────────┐                    │
  │ Cognito     │◀───────────────────┘
  │ User Pool   │         OAuth 2.0 AuthCode + PKCE
  │ (Hosted UI) │
  └─────────────┘                    │
                                     ▼
                           ┌─────────────────────┐
                           │  Secrets Manager     │
                           │  /dati/piperun/users │
                           │  /{cognito_sub}      │
                           └─────────────────────┘
```

## Stack

- **Runtime**: Python 3.13 + Lambda
- **API**: API Gateway HTTP API
- **Auth**: Cognito User Pool (OAuth 2.0 AuthCode + PKCE)
- **Secrets**: AWS Secrets Manager
- **IaC**: AWS CDK (TypeScript)
- **Observabilidade**: CloudWatch + X-Ray

## Deploy

```bash
# 1. Instalar dependências da Lambda layer
cd lambda
pip install -r requirements.txt -t layer/python --platform manylinux2014_x86_64 --only-binary=:all:

# 2. Deploy CDK
cd ../cdk
npm install
npx cdk deploy --profile dati-quick-labs
```

## Fluxo de Autenticação

1. Quick Suite descobre OAuth via `/.well-known/oauth-protected-resource`
2. Quick redireciona usuário para Cognito Hosted UI
3. Usuário faz login no Cognito (Google Workspace / email+senha)
4. Cognito emite Authorization Code → Quick troca por Access Token
5. Quick envia requests MCP com `Authorization: Bearer {access_token}`
6. Lambda valida JWT do Cognito, extrai `sub`
7. Lambda busca token PipeRun em Secrets Manager (`/dati/piperun/users/{sub}`)
8. Lambda executa chamada na API PipeRun e retorna resultado

## Cadastro do Token PipeRun (One-Time)

1. Usuário acessa endpoint `/register-token` autenticado
2. Cola o token PipeRun (obtido em https://app.pipe.run/v2/me/user-data)
3. Lambda valida o token com `GET /me` na API PipeRun
4. Token é salvo no Secrets Manager cifrado com KMS

## Tools Disponíveis

### Leitura
| Tool | Descrição |
|------|-----------|
| `piperun_listar_funis` | Lista funis e etapas disponíveis |
| `piperun_listar_deals` | Lista negócios com filtros |
| `piperun_obter_deal` | Detalhes de um deal |
| `piperun_buscar_contatos` | Busca pessoas e empresas |
| `piperun_obter_contato` | Detalhes de um contato |
| `piperun_listar_atividades` | Lista atividades |
| `piperun_listar_propostas` | Lista propostas de um deal |

### Escrita
| Tool | Descrição |
|------|-----------|
| `piperun_criar_deal` | Cria novo negócio |
| `piperun_atualizar_deal` | Atualiza campos de um deal |
| `piperun_mover_etapa` | Move deal entre etapas |
| `piperun_criar_atividade` | Cria atividade |
| `piperun_concluir_atividade` | Marca atividade como concluída |
| `piperun_criar_nota` | Adiciona nota em deal/contato |
| `piperun_criar_proposta` | Cria proposta comercial |

## Custo Estimado

~USD 50/mês para 30 usuários ativos (Lambda + API GW + Cognito + Secrets Manager)
