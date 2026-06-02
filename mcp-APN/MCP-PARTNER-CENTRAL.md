# MCP Partner Central Agents — Guia de Implementação

Configuração do MCP Server do AWS Partner Central no Amazon Q (QuickSight) para acesso a oportunidades, funding e insights de co-selling.

---

## Visão Geral

| Propriedade | Valor |
|-------------|-------|
| **Serviço** | AWS Partner Central Agents |
| **Endpoint** | `https://partnercentral-agents-mcp.us-east-1.api.aws/mcp` |
| **Região** | `us-east-1` (única disponível) |
| **Protocolo** | JSON-RPC 2.0 over HTTPS + SSE |
| **Autenticação** | AWS Signature Version 4 (SigV4) |
| **SigV4 Service Name** | `partnercentral-agents-mcp` |
| **TLS** | 1.2+ obrigatório |

### Contas Envolvidas

| Conta | ID | Função |
|-------|----|--------|
| **QuickSight (consumidor)** | `601804669442` | Onde o Amazon Q está configurado |
| **Partner Central (APN)** | `107028717321` | Onde o Partner Central está registrado |

> **Cenário Cross-Account:** O QuickSight na conta `601804669442` precisa assumir um role na conta `107028717321` para autenticar no MCP do Partner Central via SigV4.

---

## Pré-requisitos

- [ ] Conta `107028717321` com Partner Central **migrado** para o console AWS (não portal legado)
- [ ] Conta `601804669442` com QuickSight Enterprise Edition ativa em `us-east-1`
- [ ] Acesso admin ao QuickSight (conta `601804669442`)
- [ ] Acesso IAM em **ambas** as contas para criar policies e roles
- [ ] Conectividade HTTPS para `partnercentral-agents-mcp.us-east-1.api.aws`

---

## Arquitetura Cross-Account

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Conta 601804669442 (dati-quick-labs)                                       │
│                                                                             │
│  ┌──────────────┐     ┌──────────────────────────────┐                      │
│  │  QuickSight  │────▶│  QuickSight Service Role     │                      │
│  │  (Amazon Q)  │     │  (assume role cross-account) │                      │
│  └──────────────┘     └──────────────┬───────────────┘                      │
│                                      │ sts:AssumeRole                       │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────┼──────────────────────────────────────┐
│  Conta 107028717321 (APN / Partner Central)                                 │
│                                      │                                      │
│  ┌───────────────────────────────────▼──────────────────────────────┐       │
│  │  IAM Role: PartnerCentralMCPRole                                  │       │
│  │  Trust: 601804669442 (QuickSight service role)                    │       │
│  │  Permissions: partnercentral:*, aws-marketplace:*                 │       │
│  └───────────────────────────────────┬──────────────────────────────┘       │
│                                      │ SigV4                                │
│                                      ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  Partner Central Agents MCP Server                                │       │
│  │  partnercentral-agents-mcp.us-east-1.api.aws/mcp                  │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Etapa 1: Criar IAM Role na Conta APN (107028717321)

Criar um role na conta do Partner Central que o QuickSight possa assumir.

### 1.1 Trust Policy (quem pode assumir o role)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowQuickSightCrossAccount",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::601804669442:root"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "quicksight-partner-central"
                }
            }
        }
    ]
}
```

> **Nota:** Após identificar o role exato do QuickSight, restringir o Principal para o ARN específico do role (ex: `arn:aws:iam::601804669442:role/aws-quicksight-service-role-v0`).

### 1.2 Permissions Policy — Full Access

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "MCPProtocolAccess",
            "Effect": "Allow",
            "Action": [
                "partnercentral:UseSession"
            ],
            "Resource": "*",
            "Condition": {
                "Bool": {
                    "aws:IsMcpServiceAction": "true"
                }
            }
        },
        {
            "Sid": "PartnerCentralOpportunities",
            "Effect": "Allow",
            "Action": [
                "partnercentral:List*",
                "partnercentral:Get*",
                "partnercentral:UpdateOpportunity",
                "partnercentral:SubmitOpportunity",
                "partnercentral:AssignOpportunity",
                "partnercentral:AssociateOpportunity",
                "partnercentral:DisassociateOpportunity",
                "partnercentral:CreateResourceSnapshot",
                "partnercentral:CreateResourceSnapshotJob",
                "partnercentral:StartResourceSnapshotJob",
                "partnercentral:CreateEngagement",
                "partnercentral:CreateEngagementInvitation",
                "partnercentral:RejectEngagementInvitation",
                "partnercentral:StartEngagementByAcceptingInvitationTask",
                "partnercentral:StartEngagementFromOpportunityTask"
            ],
            "Resource": "*"
        },
        {
            "Sid": "PartnerCentralFunding",
            "Effect": "Allow",
            "Action": [
                "partnercentral:ListBenefitAllocations",
                "partnercentral:ListBenefitApplications",
                "partnercentral:CreateBenefitApplication",
                "partnercentral:GetBenefitApplication",
                "partnercentral:UpdateBenefitApplication",
                "partnercentral:SubmitBenefitApplication",
                "partnercentral:AmendBenefitApplication",
                "partnercentral:CancelBenefitApplication",
                "partnercentral:RecallBenefitApplication",
                "partnercentral:AssociateBenefitApplicationResource",
                "partnercentral:DisassociateBenefitApplicationResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "MarketplaceAccess",
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

### 1.3 Permissions Policy — Read-Only (recomendado para início)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "MCPProtocolAccess",
            "Effect": "Allow",
            "Action": [
                "partnercentral:UseSession"
            ],
            "Resource": "*",
            "Condition": {
                "Bool": {
                    "aws:IsMcpServiceAction": "true"
                }
            }
        },
        {
            "Sid": "PartnerCentralReadOnly",
            "Effect": "Allow",
            "Action": [
                "partnercentral:List*",
                "partnercentral:Get*"
            ],
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

### 1.4 Criar o Role (CLI)

```bash
# Executar na conta 107028717321
# Profile: <PROFILE_APN>

# Criar o role com trust policy
aws iam create-role \
    --role-name PartnerCentralMCPRole \
    --assume-role-policy-document file://trust-policy.json \
    --description "Role for QuickSight cross-account access to Partner Central MCP" \
    --profile <PROFILE_APN> \
    --region us-east-1

# Anexar permissions policy
aws iam put-role-policy \
    --role-name PartnerCentralMCPRole \
    --policy-name PartnerCentralMCPAccess \
    --policy-document file://permissions-policy.json \
    --profile <PROFILE_APN>
```

---

## Etapa 2: Configurar Permissões na Conta QuickSight (601804669442)

O role do QuickSight precisa de permissão para assumir o role cross-account.

### 2.1 Identificar o Role do QuickSight

```bash
aws quicksight describe-account-settings \
    --aws-account-id 601804669442 \
    --region us-east-1 \
    --profile dati-quick-labs
```

### 2.2 Adicionar Permissão de AssumeRole

Anexar esta inline policy ao role do QuickSight:

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
                    "sts:ExternalId": "quicksight-partner-central"
                }
            }
        }
    ]
}
```

```bash
aws iam put-role-policy \
    --role-name aws-quicksight-service-role-v0 \
    --policy-name AssumePartnerCentralMCPRole \
    --policy-document file://assume-role-policy.json \
    --profile dati-quick-labs
```

---

## Etapa 3: Configurar MCP Server no QuickSight

### Via Console

1. Acesse o QuickSight: https://us-east-1.quicksight.aws.amazon.com
2. Vá em **Admin** → **Manage extensions** → **MCP Servers**
3. Clique em **Add MCP Server**
4. Preencha:

| Campo | Valor |
|-------|-------|
| Name | `Partner Central Agents` |
| Description | `AWS Partner Central - Oportunidades, Funding e Co-Selling` |
| MCP Server Endpoint | `https://partnercentral-agents-mcp.us-east-1.api.aws/mcp` |
| Authentication type | `AWS IAM (SigV4)` |
| IAM Role ARN | `arn:aws:iam::107028717321:role/PartnerCentralMCPRole` |
| Service name | `partnercentral-agents-mcp` |
| Region | `us-east-1` |
| External ID | `quicksight-partner-central` |

5. Clique em **Save**

> **Nota:** Se o QuickSight não suportar role ARN cross-account diretamente na configuração do MCP Server, pode ser necessário configurar o role na seção de "Security & permissions" do QuickSight admin e referenciar o role lá.

### Alternativa: Configuração Direta (sem cross-account)

Se o QuickSight suportar apenas SigV4 com credenciais da própria conta, uma alternativa é:

1. Criar um **Lambda proxy** na conta `601804669442` que:
   - Recebe chamadas MCP do QuickSight
   - Assume o role na conta `107028717321`
   - Faz forward da requisição para o endpoint do Partner Central com SigV4 da conta APN
   - Retorna a resposta ao QuickSight

2. Configurar o MCP Server no QuickSight apontando para o Lambda proxy

Esta abordagem é mais complexa mas garante compatibilidade caso o QuickSight não suporte cross-account nativo para MCP.

---

## Etapa 4: Validação

### Teste de Conectividade (conta APN)

Testar que as credenciais da conta `107028717321` conseguem acessar o MCP:

```bash
# Executar com credenciais da conta 107028717321
python -c "
import boto3
import json
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

session = boto3.Session(profile_name='<PROFILE_APN>', region_name='us-east-1')
credentials = session.get_credentials().get_frozen_credentials()

url = 'https://partnercentral-agents-mcp.us-east-1.api.aws/mcp'

payload = json.dumps({
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'initialize',
    'params': {
        'protocolVersion': '2025-03-26',
        'capabilities': {},
        'clientInfo': {
            'name': 'dati-quicksight-test',
            'version': '1.0.0'
        }
    }
})

headers = {'Content-Type': 'application/json'}
request = AWSRequest(method='POST', url=url, data=payload, headers=headers)
SigV4Auth(credentials, 'partnercentral-agents-mcp', 'us-east-1').add_auth(request)

response = requests.post(url, headers=dict(request.headers), data=payload)
print(f'Status: {response.status_code}')
print(f'Response: {json.dumps(response.json(), indent=2)}')
"
```

### Teste Cross-Account (AssumeRole)

Testar que a conta `601804669442` consegue assumir o role e acessar o MCP:

```bash
# Executar com credenciais da conta 601804669442
python -c "
import boto3
import json
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Assume role na conta APN
sts = boto3.Session(profile_name='dati-quick-labs', region_name='us-east-1').client('sts')
assumed = sts.assume_role(
    RoleArn='arn:aws:iam::107028717321:role/PartnerCentralMCPRole',
    RoleSessionName='quicksight-partner-central-test',
    ExternalId='quicksight-partner-central'
)

# Usar credenciais temporárias
from botocore.credentials import Credentials
creds = Credentials(
    access_key=assumed['Credentials']['AccessKeyId'],
    secret_key=assumed['Credentials']['SecretAccessKey'],
    token=assumed['Credentials']['SessionToken']
)

url = 'https://partnercentral-agents-mcp.us-east-1.api.aws/mcp'
payload = json.dumps({
    'jsonrpc': '2.0',
    'id': 1,
    'method': 'initialize',
    'params': {
        'protocolVersion': '2025-03-26',
        'capabilities': {},
        'clientInfo': {'name': 'dati-cross-account-test', 'version': '1.0.0'}
    }
})

headers = {'Content-Type': 'application/json'}
request = AWSRequest(method='POST', url=url, data=payload, headers=headers)
SigV4Auth(creds, 'partnercentral-agents-mcp', 'us-east-1').add_auth(request)

response = requests.post(url, headers=dict(request.headers), data=payload)
print(f'Status: {response.status_code}')
print(f'Response: {json.dumps(response.json(), indent=2)}')
"
```

Resposta esperada:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "protocolVersion": "2025-03-26",
        "capabilities": {
            "tools": {
                "listChanged": false
            }
        },
        "serverInfo": {
            "name": "PartnerCentralAgentMCPServer",
            "version": "1.0.0"
        }
    }
}
```

### Teste no Amazon Q (QuickSight)

Após configurar, abra o Amazon Q no QuickSight e teste:

**Teste básico (Sandbox — sem afetar dados reais):**
```
Using the Sandbox catalog, what can you help me with in Partner Central?
```

**Listar oportunidades:**
```
List my open opportunities in Partner Central
```

**Pipeline insights:**
```
Show me opportunities with expected close date in Q2 2026
```

**Funding:**
```
What funding programs am I eligible for?
```

---

## Tools Disponíveis

O Partner Central MCP Server expõe 2 tools principais:

| Tool | Descrição |
|------|-----------|
| `sendMessage` | Enviar mensagem ao agent (linguagem natural) |
| `getSession` | Recuperar histórico de uma sessão |

### sendMessage — Parâmetros

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `content` | array | Sim | Array de content blocks (text, document) |
| `catalog` | string | Sim | `"AWS"` (produção) ou `"Sandbox"` (teste) |
| `sessionId` | string | Não | ID da sessão para continuidade (gerado automaticamente na 1ª chamada) |
| `stream` | boolean | Não | `true` para SSE streaming |
| `approvalAction` | object | Não | Aprovar/rejeitar operações de escrita |

### Catalogs

| Catalog | Uso |
|---------|-----|
| `"AWS"` | **Produção** — afeta dados reais do Partner Central |
| `"Sandbox"` | **Teste** — ambiente isolado, sem impacto em produção |

---

## Capacidades do Agent

### 1. Pipeline & Opportunity Insights
- Listar oportunidades por stage, deadline, revenue
- Identificar deals que precisam de atenção
- Resumir status do pipeline
- Flags de oportunidades próximas de deadlines

### 2. Deal Progression
- Recomendações de próximos passos por oportunidade
- Upload de transcripts de reuniões para popular campos
- Geração de sales plays sob demanda
- Atualização de campos de oportunidade

### 3. Funding Programs
- Verificar elegibilidade para MAP, POC, WMP
- Identificar oportunidades qualificadas para funding
- Criar fund requests pré-populados
- Flags de gaps para qualificação

### 4. Customer Insights
- Dados do cliente para preparar calls
- Pain points mapeados
- Compliance requirements identificados

---

## Sessões

| Propriedade | Valor |
|-------------|-------|
| Formato do ID | `session-{UUID v4}` |
| Criação | Automática na 1ª chamada `sendMessage` sem `sessionId` |
| Expiração | 48 horas (absoluta, não por inatividade) |

---

## Rate Limits

| Operação | Rate sustentado | Burst |
|----------|----------------|-------|
| `sendMessage` | 2 req/min | 10 |
| Outras operações | 10 req/min | 20 |

> Implementar exponential backoff com jitter em caso de erro `-32004` (LIMIT_EXCEEDED).

---

## Códigos de Erro

| Código | Nome | Descrição |
|--------|------|-----------|
| `-32001` | AUTHENTICATION_FAILURE | SigV4 inválido ou credenciais expiradas |
| `-31004` | TOOL_PERMISSION_DENIED | Falta permissão IAM `partnercentral:*` |
| `-32002` | ACCESS_DENIED | Conta não enrolled, região errada, etc. |
| `-32004` | LIMIT_EXCEEDED | Rate limit excedido — retry com backoff |
| `-30001` | RESOURCE_NOT_FOUND | Recurso (sessão, oportunidade) não existe |
| `-32600` | INVALID_REQUEST | JSON-RPC malformado ou parâmetros inválidos |
| `-32603` | INTERNAL_ERROR | Erro server-side — retry |

---

## Upload de Arquivos

Para enviar transcripts, notas ou documentos ao agent:

| Propriedade | Valor |
|-------------|-------|
| Max arquivos/mensagem | 3 |
| Limite imagem | 3.75 MB |
| Limite documento | 4.5 MB |
| Extensões permitidas | `doc`, `docx`, `pdf`, `png`, `jpeg`, `xlsx`, `csv`, `txt` |
| Bucket S3 (produção) | `aws-partner-central-marketplace-ephemeral-writeonly-files` |
| Path de upload | `s3://{bucket}/{aws-account-id}/` |

### Workflow de Upload

1. Upload do arquivo para o bucket S3 sob o prefixo da conta
2. Anotar o S3 URI incluindo `versionId`
3. Incluir como content block `document` no `sendMessage`

```
s3://aws-partner-central-marketplace-ephemeral-writeonly-files/107028717321/meeting-notes.pdf?versionId=abc123
```

---

## Streaming (SSE)

Quando `stream: true`, o server retorna Server-Sent Events:

| Evento | Descrição |
|--------|-----------|
| `stream_start` | Conexão SSE estabelecida |
| `assistant-response.start` | Agent começou a gerar resposta |
| `assistant-response.delta` | Chunk incremental de texto |
| `assistant-response.completed` | Resposta completa |
| `server-tool-use` | Agent invocando tool interna (read) |
| `server-tool-response` | Resultado de tool interna |
| `tool_approval_request` | Agent pedindo aprovação para write |
| `stream_end` | Conexão SSE fechando |
| `done` | Evento final do stream |

---

## Segurança

- **Não** passar credenciais AWS via parâmetros de tool — auth é via SigV4 no transport
- Usar `Sandbox` para testes — não afeta dados de produção
- Aplicar **least privilege** — começar com read-only
- Operações de escrita usam **human-in-the-loop** — agent pede aprovação antes de executar
- Sessões são **transientes** (48h) — não usar para armazenamento
- Uploads vão para bucket **efêmero** — não enviar credenciais/secrets

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Conta 601804669442 (dati-quick-labs)                                       │
│                                                                             │
│  ┌──────────────┐     ┌──────────────────────────────┐                      │
│  │  QuickSight  │────▶│  QuickSight Service Role     │──── AssumeRole ────┐ │
│  │  (Amazon Q)  │     └──────────────────────────────┘                    │ │
│  └──────────────┘                                                         │ │
└───────────────────────────────────────────────────────────────────────────┼─┘
                                                                            │
┌───────────────────────────────────────────────────────────────────────────┼─┐
│  Conta 107028717321 (APN)                                                 │ │
│                                                                           ▼ │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  IAM Role: PartnerCentralMCPRole                                  │       │
│  │  (credenciais temporárias via STS)                                │       │
│  └───────────────────────────────────┬──────────────────────────────┘       │
│                                      │ SigV4                                │
│                                      ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  Partner Central Agents MCP Server                                │       │
│  │  partnercentral-agents-mcp.us-east-1.api.aws/mcp                  │       │
│  │  (Powered by Amazon Bedrock AgentCore)                            │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                      │                                      │
│                                      ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  AWS Partner Central                                              │       │
│  │  (Opportunities, Funding, Engagements, Marketplace)               │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Diferenças vs MCPs Existentes (PipeRun/Factorial)

| Aspecto | PipeRun / Factorial | Partner Central |
|---------|--------------------:|----------------:|
| **Auth** | OAuth (token endpoint) | SigV4 (IAM cross-account) |
| **Infra** | Lambda própria | Managed pela AWS |
| **Deploy** | CDK stack na conta | Nenhum (SaaS) |
| **Cross-account** | Não (mesma conta) | Sim (601804669442 → 107028717321) |
| **Custo** | ~$1-2/mês (Lambda+Secrets) | $0 (incluso no Partner) |
| **Manutenção** | Nossa responsabilidade | AWS mantém |
| **Tools** | Múltiplas tools específicas | 2 tools (sendMessage, getSession) |
| **Interação** | Chamada direta por tool | Conversacional (linguagem natural) |

---

## Checklist de Implementação

### Conta APN (107028717321)
- [ ] Verificar que Partner Central está migrado para console AWS
- [ ] Criar IAM Role `PartnerCentralMCPRole` com trust policy
- [ ] Anexar permissions policy (read-only ou full)
- [ ] Testar conectividade direta ao MCP com credenciais da conta

### Conta QuickSight (601804669442)
- [ ] Identificar o service role do QuickSight
- [ ] Adicionar policy de `sts:AssumeRole` para o role cross-account
- [ ] Configurar MCP Server no console do QuickSight
- [ ] Testar cross-account AssumeRole via CLI
- [ ] Validar no Amazon Q com pergunta de teste

### Pós-implementação
- [ ] Documentar no `docs/MCP-SERVERS.md` (tabela de visão geral)
- [ ] Definir quais usuários/grupos terão acesso ao MCP no QuickSight
- [ ] Avaliar upgrade de read-only para full access após validação

---

## Referências

- [Partner Central MCP Server — Overview](https://docs.aws.amazon.com/partner-central/latest/APIReference/partner-central-mcp-server.html)
- [Getting Started Guide](https://docs.aws.amazon.com/partner-central/latest/APIReference/mcp-getting-started.html)
- [Configuration Reference](https://docs.aws.amazon.com/partner-central/latest/APIReference/mcp-configuration-reference.html)
- [Tools Reference](https://docs.aws.amazon.com/partner-central/latest/APIReference/mcp-tools-reference.html)
- [Migration Guide (Partner Central)](https://docs.aws.amazon.com/partner-central/latest/getting-started/partner-admin-section.html)
