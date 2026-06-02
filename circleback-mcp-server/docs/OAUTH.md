# Autenticação OAuth - Circleback MCP Server

## Visão Geral

O servidor atua como um **OAuth Authorization Server intermediário** entre o Amazon QuickSight e o Circleback.ai. Utiliza PKCE (Proof Key for Code Exchange) com método S256 para segurança adicional.

## Componentes

### Credenciais QuickSight → Lambda

O QuickSight se autentica com o Lambda usando:

| Parâmetro | Valor |
|-----------|-------|
| Client ID | `circleback-quicksight-mcp` |
| Client Secret | `dati-qs-circleback-2024-secret` |

### Credenciais Lambda → Circleback

O Lambda se registra dinamicamente no Circleback como **public client** (sem client_secret). O `client_id` é obtido via Dynamic Client Registration e armazenado no DynamoDB.

## Fluxo Detalhado

### Passo 1: QuickSight inicia autorização

```
GET /oauth/authorize?client_id=circleback-quicksight-mcp&redirect_uri=<qs_callback>&state=<qs_state>&response_type=code
```

O Lambda:
1. Valida o `client_id` do QuickSight
2. Gera `code_verifier` (32 bytes random, base64url)
3. Calcula `code_challenge = SHA256(code_verifier)` em base64url
4. Salva no DynamoDB: `{ state, qs_redirect_uri, qs_state, code_verifier }` com TTL de 10 min
5. Redireciona o browser para o Circleback com `code_challenge`

### Passo 2: Usuário autoriza no Circleback

O Circleback exibe tela de consentimento. Após aprovação, redireciona para:

```
GET /oauth/circleback-callback?code=<circleback_code>&state=<internal_state>
```

### Passo 3: Lambda troca code com PKCE

O Lambda:
1. Recupera `{ qs_redirect_uri, qs_state, code_verifier }` do DynamoDB pelo state
2. Envia `POST` ao Circleback token endpoint com `code_verifier`:

```
POST https://circleback.ai/api/oauth/access-token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<circleback_code>
&client_id=<dynamic_client_id>
&redirect_uri=<callback_url>
&code_verifier=<stored_verifier>
```

3. Recebe `access_token` + `refresh_token` do Circleback
4. Gera um code interno (UUID) para o QuickSight
5. Salva tokens vinculados ao code interno no DynamoDB
6. Redireciona para o QuickSight: `<qs_redirect_uri>?code=<internal_code>&state=<qs_state>`

### Passo 4: QuickSight troca code por token

```
POST /oauth/token
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "<internal_code>",
  "client_id": "circleback-quicksight-mcp",
  "client_secret": "dati-qs-circleback-2024-secret"
}
```

Resposta:

```json
{
  "access_token": "<circleback_access_token>",
  "refresh_token": "<circleback_refresh_token>",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

O code interno é **uso único** — deletado imediatamente após exchange.

### Passo 5: Refresh Token

```
POST /oauth/token
Content-Type: application/json

{
  "grant_type": "refresh_token",
  "refresh_token": "<refresh_token>",
  "client_id": "circleback-quicksight-mcp",
  "client_secret": "dati-qs-circleback-2024-secret"
}
```

O Lambda faz refresh diretamente no Circleback e retorna os novos tokens ao QuickSight.

## Circleback OAuth Endpoints

| Endpoint | URL |
|----------|-----|
| Authorization | `https://circleback.ai/api/oauth/authorize` |
| Token | `https://circleback.ai/api/oauth/access-token` |
| Registration | `https://circleback.ai/api/oauth/register` |

## Dynamic Client Registration

Na primeira execução, o Lambda se registra automaticamente no Circleback:

```json
POST https://circleback.ai/api/oauth/register

{
  "client_name": "Amazon QuickSight - Dati Quick Labs",
  "redirect_uris": ["<base_url>/oauth/circleback-callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

O `client_id` retornado é salvo no DynamoDB com chave `__circleback_client__` para reutilização.

## Armazenamento de Estado (DynamoDB)

| Chave (userId) | Conteúdo | TTL |
|----------------|----------|-----|
| `oauth_state#<state>` | JSON com redirect_uri, qs_state, code_verifier | 10 min |
| `code#<internal_code>` | access_token, refresh_token, expiresAt | — |
| `__circleback_client__` | client_id do Circleback | 1 ano |

## Segurança

- **PKCE S256**: Protege contra interceptação de authorization codes
- **State parameter**: Previne CSRF
- **Codes de uso único**: Deletados após exchange
- **TTL no DynamoDB**: States expiram automaticamente em 10 minutos
- **Validação de client_id/secret**: Apenas o QuickSight configurado pode trocar tokens
