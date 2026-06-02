# MCP Partner Central — Passo a Passo de Implementação

## Contexto

O QuickSight **não suporta SigV4** para conectar a MCP Servers. Ele exige:
- Client ID
- Client Secret
- Authorization URL
- Token URL

Portanto, precisamos criar uma **camada proxy** que:
1. Exponha um endpoint MCP compatível com OAuth 2.0 (para o QuickSight)
2. Internamente assuma o role na conta APN e faça SigV4 para o Partner Central

---

## Arquitetura Final

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Conta 601804669442 (dati-quick-labs) — Profile: dati-quick-labs                │
│                                                                                 │
│  ┌──────────────┐     OAuth 2.0      ┌──────────────────────────────────┐       │
│  │  QuickSight  │───────────────────▶│  API Gateway (HTTP API)          │       │
│  │  (Amazon Q)  │  Client Credentials │  POST /mcp                       │       │
│  └──────────────┘                     └──────────────┬───────────────────┘       │
│                                                      │                           │
│  ┌──────────────────────────────────────────────────┐│                           │
│  │  Cognito User Pool                               ││                           │
│  │  - App Client (client_id + client_secret)        ││                           │
│  │  - OAuth 2.0 endpoints (authorize, token)        ││                           │
│  │  - Resource Server (scope: mcp/invoke)           ││                           │
│  └──────────────────────────────────────────────────┘│                           │
│                                                      │ Authorizer                │
│                                                      ▼                           │
│  ┌──────────────────────────────────────────────────────────────────────┐       │
│  │  Lambda: partner-central-mcp-proxy                                    │       │
│  │  1. Valida token (via API GW authorizer)                              │       │
│  │  2. Assume Role na conta APN (sts:AssumeRole)                         │       │
│  │  3. Assina request com SigV4 (service: partnercentral-agents-mcp)     │       │
│  │  4. Forward para Partner Central MCP endpoint                         │       │
│  │  5. Retorna resposta ao QuickSight                                    │       │
│  └──────────────────────────────────────────────────────┬───────────────┘       │
│                                                          │ sts:AssumeRole        │
└──────────────────────────────────────────────────────────┼───────────────────────┘
                                                           │
┌──────────────────────────────────────────────────────────┼───────────────────────┐
│  Conta 107028717321 (APN) — Profile: dati-apn            │                       │
│                                                          ▼                       │
│  ┌──────────────────────────────────────────────────────────────────────┐       │
│  │  IAM Role: PartnerCentralMCPRole                                      │       │
│  │  Trust: Lambda role da conta 601804669442                             │       │
│  │  Permissions: partnercentral:*, aws-marketplace:*                     │       │
│  └──────────────────────────────────────────────────────┬───────────────┘       │
│                                                          │ SigV4                 │
│                                                          ▼                       │
│  ┌──────────────────────────────────────────────────────────────────────┐       │
│  │  Partner Central Agents MCP Server                                    │       │
│  │  https://partnercentral-agents-mcp.us-east-1.api.aws/mcp             │       │
│  └──────────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Profiles AWS CLI

| Profile | Conta | Uso |
|---------|-------|-----|
| `dati-quick-labs` | `601804669442` | QuickSight, Cognito, API GW, Lambda |
| `dati-apn` | `107028717321` | Partner Central, IAM Role |

---

## Etapas

### Etapa 1 — IAM Role na Conta APN (107028717321)

**Objetivo:** Criar role que o Lambda da conta QuickSight possa assumir.

#### 1.1 Trust Policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowLambdaProxyCrossAccount",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::601804669442:root"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "partner-central-mcp-proxy"
                }
            }
        }
    ]
}
```

> Após criar o Lambda role, restringir o Principal para o ARN exato (ex: `arn:aws:iam::601804669442:role/partner-central-mcp-proxy-role`).

#### 1.2 Permissions Policy (Read-Only para começar)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "MCPProtocolAccess",
            "Effect": "Allow",
            "Action": ["partnercentral:UseSession"],
            "Resource": "*",
            "Condition": {
                "Bool": { "aws:IsMcpServiceAction": "true" }
            }
        },
        {
            "Sid": "PartnerCentralReadOnly",
            "Effect": "Allow",
            "Action": ["partnercentral:List*", "partnercentral:Get*"],
            "Resource": "*"
        },
        {
            "Sid": "MarketplaceReadOnly",
            "Effect": "Allow",
            "Action": [
                "aws-marketplace:DescribeEntity",
                "aws-marketplace:DescribeAgreement",
                "aws-marketplace:SearchAgreements",
                "aws-marketplace:ListEntities"
            ],
            "Resource": "*"
        }
    ]
}
```

#### 1.3 Comandos

```bash
# Criar role
aws iam create-role \
    --role-name PartnerCentralMCPRole \
    --assume-role-policy-document file://trust-policy.json \
    --description "Role for Lambda proxy cross-account access to Partner Central MCP" \
    --profile dati-apn \
    --region us-east-1

# Anexar permissions
aws iam put-role-policy \
    --role-name PartnerCentralMCPRole \
    --policy-name PartnerCentralMCPReadOnly \
    --policy-document file://permissions-readonly.json \
    --profile dati-apn
```

---

### Etapa 2 — Cognito User Pool (601804669442)

**Objetivo:** Fornecer Client ID, Client Secret e endpoints OAuth para o QuickSight.

#### 2.1 Criar User Pool

```bash
aws cognito-idp create-user-pool \
    --pool-name partner-central-mcp-auth \
    --profile dati-quick-labs \
    --region us-east-1
```

#### 2.2 Criar Resource Server (define scopes)

```bash
aws cognito-idp create-resource-server \
    --user-pool-id <USER_POOL_ID> \
    --identifier "mcp" \
    --name "MCP Partner Central" \
    --scopes ScopeName=invoke,ScopeDescription="Invoke MCP Partner Central" \
    --profile dati-quick-labs \
    --region us-east-1
```

#### 2.3 Criar Domain (para endpoints OAuth)

```bash
aws cognito-idp create-user-pool-domain \
    --domain partner-central-mcp \
    --user-pool-id <USER_POOL_ID> \
    --profile dati-quick-labs \
    --region us-east-1
```

Isso gera os endpoints:
- **Authorization URL:** `https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/authorize`
- **Token URL:** `https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/token`

#### 2.4 Criar App Client (Client Credentials flow)

```bash
aws cognito-idp create-user-pool-client \
    --user-pool-id <USER_POOL_ID> \
    --client-name quicksight-mcp-client \
    --generate-secret \
    --allowed-o-auth-flows client_credentials \
    --allowed-o-auth-scopes mcp/invoke \
    --allowed-o-auth-flows-user-pool-client \
    --profile dati-quick-labs \
    --region us-east-1
```

**Output:** Anotar `ClientId` e `ClientSecret` — são os valores para configurar no QuickSight.

#### 2.5 Resumo dos valores para o QuickSight

| Campo QuickSight | Valor |
|------------------|-------|
| Client ID | `<ClientId do App Client>` |
| Client Secret | `<ClientSecret do App Client>` |
| Authorization URL | `https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/authorize` |
| Token URL | `https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/token` |

---

### Etapa 3 — Lambda Proxy (601804669442)

**Objetivo:** Receber chamadas MCP do QuickSight, assumir role na APN, e fazer forward com SigV4.

#### 3.1 IAM Role do Lambda

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AssumePartnerCentralRole",
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Resource": "arn:aws:iam::107028717321:role/PartnerCentralMCPRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "partner-central-mcp-proxy"
                }
            }
        },
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:us-east-1:601804669442:*"
        }
    ]
}
```

#### 3.2 Código Lambda (Python)

```python
import json
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import urllib3

http = urllib3.PoolManager()

MCP_ENDPOINT = "https://partnercentral-agents-mcp.us-east-1.api.aws/mcp"
ROLE_ARN = "arn:aws:iam::107028717321:role/PartnerCentralMCPRole"
EXTERNAL_ID = "partner-central-mcp-proxy"
SERVICE_NAME = "partnercentral-agents-mcp"
REGION = "us-east-1"

sts_client = boto3.client("sts", region_name=REGION)


def get_assumed_credentials():
    """Assume role na conta APN e retorna credenciais temporárias."""
    response = sts_client.assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName="mcp-proxy-session",
        ExternalId=EXTERNAL_ID,
        DurationSeconds=900
    )
    creds = response["Credentials"]
    return Credentials(
        access_key=creds["AccessKeyId"],
        secret_key=creds["SecretAccessKey"],
        token=creds["SessionToken"]
    )


def sign_and_forward(payload: str) -> dict:
    """Assina a request com SigV4 e faz forward para o MCP endpoint."""
    credentials = get_assumed_credentials()

    headers = {"Content-Type": "application/json"}
    request = AWSRequest(method="POST", url=MCP_ENDPOINT, data=payload, headers=headers)
    SigV4Auth(credentials, SERVICE_NAME, REGION).add_auth(request)

    response = http.request(
        "POST",
        MCP_ENDPOINT,
        body=payload.encode("utf-8"),
        headers=dict(request.headers)
    )

    return {
        "statusCode": response.status,
        "headers": {"Content-Type": "application/json"},
        "body": response.data.decode("utf-8")
    }


def handler(event, context):
    """Handler principal — recebe JSON-RPC do QuickSight e faz proxy."""
    try:
        # Body pode vir como string ou já parseado
        body = event.get("body", "{}")
        if isinstance(body, dict):
            body = json.dumps(body)

        return sign_and_forward(body)

    except Exception as e:
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Proxy error: {str(e)}"
            }
        }
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(error_response)
        }
```

#### 3.3 Deploy Lambda

```bash
# Criar role de execução
aws iam create-role \
    --role-name partner-central-mcp-proxy-role \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --profile dati-quick-labs

# Anexar policy de AssumeRole + Logs
aws iam put-role-policy \
    --role-name partner-central-mcp-proxy-role \
    --policy-name MCPProxyPermissions \
    --policy-document file://lambda-policy.json \
    --profile dati-quick-labs

# Empacotar e criar Lambda
zip lambda.zip lambda_function.py
aws lambda create-function \
    --function-name partner-central-mcp-proxy \
    --runtime python3.12 \
    --handler lambda_function.handler \
    --role arn:aws:iam::601804669442:role/partner-central-mcp-proxy-role \
    --zip-file fileb://lambda.zip \
    --timeout 30 \
    --memory-size 256 \
    --region us-east-1 \
    --profile dati-quick-labs
```

---

### Etapa 4 — API Gateway (601804669442)

**Objetivo:** Expor o Lambda como endpoint HTTP com autenticação OAuth via Cognito.

#### 4.1 Criar HTTP API

```bash
aws apigatewayv2 create-api \
    --name partner-central-mcp \
    --protocol-type HTTP \
    --profile dati-quick-labs \
    --region us-east-1
```

#### 4.2 Criar Authorizer (JWT / Cognito)

```bash
aws apigatewayv2 create-authorizer \
    --api-id <API_ID> \
    --authorizer-type JWT \
    --name cognito-mcp-auth \
    --identity-source '$request.header.Authorization' \
    --jwt-configuration Issuer=https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>,Audience=<CLIENT_ID> \
    --profile dati-quick-labs \
    --region us-east-1
```

#### 4.3 Criar Integration (Lambda)

```bash
aws apigatewayv2 create-integration \
    --api-id <API_ID> \
    --integration-type AWS_PROXY \
    --integration-uri arn:aws:lambda:us-east-1:601804669442:function:partner-central-mcp-proxy \
    --payload-format-version 2.0 \
    --profile dati-quick-labs \
    --region us-east-1
```

#### 4.4 Criar Route com Authorizer

```bash
aws apigatewayv2 create-route \
    --api-id <API_ID> \
    --route-key "POST /mcp" \
    --authorization-type JWT \
    --authorizer-id <AUTHORIZER_ID> \
    --authorization-scopes mcp/invoke \
    --target integrations/<INTEGRATION_ID> \
    --profile dati-quick-labs \
    --region us-east-1
```

#### 4.5 Deploy

```bash
aws apigatewayv2 create-stage \
    --api-id <API_ID> \
    --stage-name prod \
    --auto-deploy \
    --profile dati-quick-labs \
    --region us-east-1
```

**Endpoint final:** `https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/mcp`

---

### Etapa 5 — Configurar MCP Server no QuickSight

1. Acesse: https://us-east-1.quicksight.aws.amazon.com
2. **Admin** → **Manage extensions** → **MCP Servers** → **Add MCP Server**

| Campo | Valor |
|-------|-------|
| Name | `Partner Central Agents` |
| Description | `AWS Partner Central - Oportunidades, Funding e Co-Selling` |
| MCP Server Endpoint | `https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/mcp` |
| Authentication type | `OAuth 2.0` |
| Client ID | `<Cognito App Client ID>` |
| Client Secret | `<Cognito App Client Secret>` |
| Authorization URL | `https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/authorize` |
| Token URL | `https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/token` |
| Scope | `mcp/invoke` |

3. **Save**

---

### Etapa 6 — Validação

#### 6.1 Testar Token OAuth (local)

```bash
# Obter token via client_credentials
curl -X POST https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials&client_id=<CLIENT_ID>&client_secret=<CLIENT_SECRET>&scope=mcp/invoke"
```

#### 6.2 Testar Proxy (com token)

```bash
TOKEN="<access_token do passo anterior>"

curl -X POST https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/mcp \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "dati-proxy-test", "version": "1.0.0"}
        }
    }'
```

**Resposta esperada:**
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "protocolVersion": "2025-03-26",
        "capabilities": { "tools": { "listChanged": false } },
        "serverInfo": { "name": "PartnerCentralAgentMCPServer", "version": "1.0.0" }
    }
}
```

#### 6.3 Testar no Amazon Q (QuickSight)

```
Using the Sandbox catalog, list my open opportunities in Partner Central
```

---

## Checklist Atualizado

### Conta APN (107028717321) — Profile: `dati-apn`
- [ ] Verificar Partner Central migrado para console AWS
- [ ] Criar IAM Role `PartnerCentralMCPRole` com trust policy
- [ ] Anexar permissions policy (read-only)
- [ ] Testar conectividade direta ao MCP

### Conta QuickSight (601804669442) — Profile: `dati-quick-labs`
- [ ] Criar Cognito User Pool
- [ ] Criar Resource Server com scope `mcp/invoke`
- [ ] Criar Domain (`partner-central-mcp`)
- [ ] Criar App Client (client_credentials)
- [ ] Criar Lambda `partner-central-mcp-proxy`
- [ ] Criar API Gateway HTTP API com JWT authorizer
- [ ] Configurar route POST /mcp → Lambda
- [ ] Testar token OAuth localmente
- [ ] Testar proxy endpoint com curl
- [ ] Configurar MCP Server no QuickSight (OAuth)
- [ ] Validar no Amazon Q

### Pós-implementação
- [ ] Documentar no `docs/MCP-SERVERS.md`
- [ ] Definir usuários/grupos com acesso
- [ ] Avaliar upgrade para full access

---

## Custos Estimados

| Recurso | Custo |
|---------|-------|
| Cognito User Pool | $0 (< 50k MAU free tier) |
| API Gateway HTTP API | ~$1/mês (1M requests = $1) |
| Lambda | ~$0.50/mês (256MB, <1s, baixo volume) |
| **Total** | **~$1.50/mês** |

---

## Próximos Passos (Ordem de Execução)

1. ✅ Documentação (este arquivo)
2. ⬜ Etapa 1 — Role na conta APN
3. ⬜ Etapa 2 — Cognito na conta QuickSight
4. ⬜ Etapa 3 — Lambda proxy
5. ⬜ Etapa 4 — API Gateway
6. ⬜ Etapa 5 — Configurar no QuickSight
7. ⬜ Etapa 6 — Validação end-to-end
