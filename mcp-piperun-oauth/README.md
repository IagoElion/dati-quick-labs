# MCP PipeRun com OAuth (Token por Usuário)

MCP Server para o PipeRun CRM que permite cada usuário autenticar com seu próprio token. Quando adicionado no Amazon Q (QuickSight), abre uma página de login onde o usuário cola seu token pessoal do PipeRun.

## Arquitetura

```
┌──────────────┐     ┌─────────────────────────────────┐     ┌─────────────┐
│  QuickSight  │────▶│  Lambda Function URL            │────▶│ PipeRun API │
│  (Amazon Q)  │     │                                 │     │ api.pipe.run│
└──────────────┘     │  /.well-known/* → OAuth metadata│     └─────────────┘
       │             │  /mcp (GET+POST) → MCP + OAuth  │
       │             │  /login (POST) → Recebe token   │
       │             │  /token (POST) → Token exchange │
       ▼             │  /register (POST) → Client reg  │
  ┌─────────┐        └─────────────────────────────────┘
  │ Browser │                       │
  │ (Login) │                       ▼
  └─────────┘              ┌─────────────────┐
                           │    DynamoDB     │
                           │ (tokens/sessões)│
                           └─────────────────┘
```

## Fluxo de Autenticação

```
1. Usuário adiciona o MCP endpoint no QuickSight
2. QuickSight faz POST /mcp → recebe 401 Unauthorized
3. QuickSight lê /.well-known/oauth-authorization-server → descobre endpoints
4. QuickSight redireciona browser para /mcp?response_type=code&...
5. Lambda exibe página HTML "Cole seu token PipeRun"
6. Usuário cola o token e clica "Autorizar"
7. Lambda valida o token com GET /me na API PipeRun
8. Lambda salva token no DynamoDB, gera session_token
9. Lambda redireciona para QuickSight com code=session_token
10. QuickSight chama POST /token com o code
11. Lambda retorna access_token (= session_token)
12. QuickSight usa access_token nas próximas requests MCP
13. Lambda busca o token PipeRun do DynamoDB e faz as chamadas
```

## Diferença do MCP PipeRun Original

| | MCP PipeRun (original) | MCP PipeRun OAuth (este) |
|---|---|---|
| **Auth** | Token único no Secrets Manager | Token por usuário no DynamoDB |
| **Login** | Nenhum (token fixo) | Página HTML no browser |
| **Multi-usuário** | Não (todos usam mesmo token) | Sim (cada um com seu token) |
| **Segurança** | Token compartilhado | Token individual, validado |
| **Endpoint** | API Gateway | Lambda Function URL |

## Tools Disponíveis (19 - read-only)

| Tool | Descrição |
|------|-----------|
| `list_opportunities` | Listar oportunidades com filtros |
| `get_opportunity` | Detalhes de uma oportunidade |
| `list_companies` | Listar empresas |
| `get_company` | Detalhes de uma empresa |
| `list_persons` | Listar pessoas/contatos |
| `get_person` | Detalhes de uma pessoa |
| `list_pipelines` | Listar funis de vendas |
| `get_pipeline` | Detalhes de um funil |
| `list_stages` | Listar etapas de funil |
| `list_activities` | Listar atividades |
| `list_proposals` | Listar propostas |
| `get_proposal` | Detalhes de uma proposta |
| `list_notes` | Listar notas |
| `list_users` | Listar usuários |
| `list_teams` | Listar equipes |
| `list_tags` | Listar tags |
| `list_sources` | Listar origens |
| `list_items` | Listar itens (produtos/serviços) |
| `list_custom_fields` | Listar campos customizados |

## Deploy

### Pré-requisitos

- Python 3.13+
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS CLI configurado
- Conta AWS com CDK bootstrapped

### Passos

```bash
# 1. Instalar dependências da layer
pip install requests aws-lambda-powertools \
  -t mcp-piperun-oauth/layer/python \
  --platform manylinux2014_x86_64 \
  --only-binary=:all:

# 2. Deploy
cd mcp-piperun-oauth/cdk
pip install -r requirements.txt
cdk deploy --profile SEU_PROFILE
```

### Após o deploy

1. Copie a **Function URL** do output
2. Atualize a variável `API_BASE_URL` na Lambda com essa URL
3. No QuickSight, adicione como MCP server endpoint: `{FUNCTION_URL}/mcp`

## Configuração no QuickSight

No Amazon Q (QuickSight), ao adicionar o MCP connector:

| Campo | Valor |
|-------|-------|
| **MCP Server Endpoint** | `https://{FUNCTION_URL}/mcp` |

Não precisa preencher OAuth fields — o server implementa o MCP Authorization spec automaticamente.

## Como o Usuário Obtém o Token

1. Acesse https://app.pipe.run/v2/me/user-data
2. O token aparece abaixo da foto do usuário
3. Ou acesse Configurações → Integrações → API

## Segurança

- Tokens são armazenados no DynamoDB com TTL de 30 dias
- Cada sessão tem um token único (hash SHA-256 como chave)
- O token PipeRun é validado com `GET /me` antes de ser aceito
- Sem token compartilhado — cada usuário usa suas próprias permissões
- Lambda Function URL com CORS configurado
- Nenhuma credencial exposta no código

## Custos Estimados

- **Lambda Function URL**: ~$0.20/mês (uso moderado)
- **DynamoDB on-demand**: ~$0.25/mês
- **Total**: ~$0.50/mês
