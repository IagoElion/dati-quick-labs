# Infraestrutura - Circleback MCP Server

## Visão Geral

O projeto oferece duas opções de deploy na AWS, ambas criando os mesmos recursos:

| Opção | Ferramenta | Arquivo |
|-------|-----------|---------|
| 1 | Serverless Framework | `serverless.yml` |
| 2 | AWS CDK (Python) | `infra/stack.py` |

## Recursos AWS

### Lambda Function

| Propriedade | Valor |
|-------------|-------|
| Nome | `circleback-mcp-server` |
| Runtime | Node.js 18.x |
| Handler | `src/index.handler` |
| Memória | 256 MB |
| Timeout | 30 segundos |
| Log Retention | 14 dias |

### API Gateway (REST)

| Propriedade | Valor |
|-------------|-------|
| Tipo | REST API |
| Stage | `prod` |
| CORS | Habilitado (all origins) |
| Integração | Lambda Proxy (ANY /{proxy+}) |
| Headers permitidos | Content-Type, x-user-id, Authorization |

### DynamoDB

| Propriedade | Valor |
|-------------|-------|
| Nome | `circleback-mcp-tokens` |
| Partition Key | `userId` (String) |
| Billing | PAY_PER_REQUEST (on-demand) |
| TTL | Habilitado (campo `ttl`) |
| Removal Policy | RETAIN |

## Deploy com Serverless Framework

### Pré-requisitos

```bash
npm install -g serverless
aws configure --profile dati-quick-labs
```

### Comandos

```bash
# Deploy em produção
npx serverless deploy --stage prod

# Deploy em staging
npx serverless deploy --stage staging

# Remover stack
npx serverless remove --stage prod

# Invocar localmente
npx serverless invoke local -f api -p events/test.json

# Desenvolvimento offline
npx serverless offline
```

### Variáveis de Ambiente (auto-geradas)

```yaml
TOKEN_TABLE: circleback-mcp-server-tokens-prod
NODE_ENV: production
CIRCLEBACK_REDIRECT_URI: https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/oauth/callback
```

### Permissões IAM

```yaml
- Effect: Allow
  Action:
    - dynamodb:GetItem
    - dynamodb:PutItem
    - dynamodb:DeleteItem
  Resource: !GetAtt TokensTable.Arn
```

## Deploy com AWS CDK

### Pré-requisitos

```bash
pip install aws-cdk-lib constructs
npm install -g aws-cdk
```

### Comandos

```bash
cd infra

# Instalar dependências Python
pip install -r requirements.txt

# Sintetizar template CloudFormation
cdk synth

# Deploy
cdk deploy

# Diff (ver mudanças antes de aplicar)
cdk diff

# Destruir stack
cdk destroy
```

### Configuração (infra/app.py)

```python
CirclebackMcpStack(
    app,
    "circleback-mcp-server",
    env=cdk.Environment(account="601804669442", region="us-east-1"),
)
```

### Outputs do CDK

| Output | Descrição |
|--------|-----------|
| `ApiUrl` | URL base do API Gateway |
| `McpEndpoint` | URL completa do endpoint MCP |
| `OAuthLoginUrl` | URL para usuários iniciarem login |
| `TokensTableName` | Nome da tabela DynamoDB criada |

## Diagrama de Recursos

```
┌─────────────────────────────────────────────────────────┐
│                     AWS Account                          │
│                   (601804669442)                         │
│                                                         │
│  ┌───────────────┐     ┌────────────────────────────┐  │
│  │  API Gateway  │────>│  Lambda Function           │  │
│  │  (REST API)   │     │  circleback-mcp-server     │  │
│  │               │     │                            │  │
│  │  /health      │     │  Express App               │  │
│  │  /oauth/*     │     │  + serverless-http         │  │
│  │  /mcp         │     │                            │  │
│  └───────────────┘     └─────────────┬──────────────┘  │
│                                      │                  │
│                                      ▼                  │
│                         ┌────────────────────────────┐  │
│                         │  DynamoDB                   │  │
│                         │  circleback-mcp-tokens      │  │
│                         │                            │  │
│                         │  PK: userId                │  │
│                         │  TTL: ttl                   │  │
│                         └────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  CloudWatch Logs (retenção: 14 dias)              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Custos Estimados

Todos os recursos utilizam modelo pay-per-use:

| Recurso | Modelo de Custo |
|---------|-----------------|
| Lambda | Primeiras 1M requests/mês gratuitas |
| API Gateway | $3.50 por milhão de requests |
| DynamoDB | $1.25 por milhão de writes, $0.25 por milhão de reads |
| CloudWatch | $0.50/GB de logs ingeridos |

Para uso típico (< 1000 chamadas MCP/dia), o custo mensal fica abaixo de **$1 USD**.
