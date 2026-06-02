# MCP PipeRun White

MCP Server white-label para o PipeRun CRM com **leitura e escrita**. Deployado na AWS como Lambda + Function URL com OAuth para funcionar no QuickSight (Amazon Q).

## Diferença do MCP PipeRun Original

| | mcp-piperun (original) | **mcp-piperun-white** (este) |
|---|---|---|
| **Operações** | Read-only (19 tools) | **Leitura + Escrita (27 tools)** |
| **Infra** | Lambda + Function URL | Lambda + Function URL |
| **Auth** | OAuth client_credentials | OAuth client_credentials |
| **Secret** | `mcp-piperun/api-token` | `mcp-piperun-white/api-token` |
| **Stack** | `McpPiperunStack` | `McpPiperunWhiteStack` |

## Tools Disponíveis (27)

### Leitura (19)
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

### Escrita (8)

| Tool | Descrição |
|------|-----------|
| `create_opportunity` | Criar nova oportunidade |
| `update_opportunity` | Atualizar oportunidade (mover etapa, valor, status) |
| `create_company` | Criar empresa |
| `update_company` | Atualizar empresa |
| `create_person` | Criar pessoa/contato |
| `update_person` | Atualizar pessoa |
| `create_activity` | Criar atividade em uma oportunidade |
| `create_note` | Criar nota em uma oportunidade |

## Deploy

### Pré-requisitos

- Python 3.13+
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS CLI configurado

### Passos

```bash
# 1. Instalar dependências da layer
pip install requests -t layer/python --platform manylinux2014_x86_64 --only-binary=:all:

# 2. Deploy
cd cdk
pip install -r requirements.txt
cdk deploy

# 3. Atualizar o secret com o token real do PipeRun
aws secretsmanager put-secret-value \
  --secret-id mcp-piperun-white/api-token \
  --secret-string '{"token": "SEU_TOKEN_PIPERUN_AQUI"}'
```

## Configuração no QuickSight

No Amazon Q (QuickSight), adicione como MCP connector:

| Campo | Valor |
|-------|-------|
| **MCP Server Endpoint** | `{FunctionUrl}mcp` (output do CDK) |

## Estrutura

```
mcp-piperun-white/
├── lambda/
│   ├── handler.py          # Handler Lambda com todas as tools
│   └── requirements.txt    # Deps da Lambda (referência)
├── layer/                   # Layer com requests (criada no deploy)
├── cdk/
│   ├── app.py              # CDK App
│   ├── stack.py            # Stack CDK
│   ├── cdk.json
│   └── requirements.txt    # Deps do CDK
├── pyproject.toml
└── README.md
```

## Como Adicionar Novas Tools

1. Crie a função `tool_xxx(params)` no `lambda/handler.py`
2. Adicione ao dict `TOOLS`
3. Adicione o schema em `MCP_TOOLS_SCHEMA`
4. Redeploy: `cd cdk && cdk deploy`
