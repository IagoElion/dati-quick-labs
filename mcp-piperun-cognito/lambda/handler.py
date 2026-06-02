"""
MCP PipeRun - Lambda Handler com Cognito OAuth + Secrets Manager
Arquitetura 5 camadas: Quick → API GW → Lambda → Cognito/Secrets → PipeRun API
Cada usuário tem token PipeRun individual no Secrets Manager.
"""

import json
import os
import time
from typing import Any

import boto3
import jwt
import requests
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from jwt import PyJWKClient
from signup_page import SIGNUP_PAGE_HTML

logger = Logger(service="mcp-piperun-cognito")
tracer = Tracer(service="mcp-piperun-cognito")
metrics = Metrics(service="mcp-piperun-cognito", namespace="MCPPipeRunCognito")

# Environment variables
PIPERUN_BASE_URL = os.environ.get("PIPERUN_BASE_URL", "https://api.pipe.run/v1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_REGION = os.environ.get("COGNITO_REGION", "us-east-1")
COGNITO_APP_CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID", "")
COGNITO_LOGIN_CLIENT_ID = os.environ.get("COGNITO_LOGIN_CLIENT_ID", "")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "")
SECRETS_PREFIX = os.environ.get("SECRETS_PREFIX", "/dati/piperun/users")

# AWS clients
secrets_client = boto3.client("secretsmanager")
_jwks_client = None
_jwks_cache_time = 0


# =============================================================================
# JWT VALIDATION (Cognito)
# =============================================================================

def get_jwks_client() -> PyJWKClient:
    """Get cached JWKS client for Cognito token validation."""
    global _jwks_client, _jwks_cache_time
    now = time.time()
    if not _jwks_client or (now - _jwks_cache_time) > 3600:
        jwks_url = (
            f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com"
            f"/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        )
        _jwks_client = PyJWKClient(jwks_url)
        _jwks_cache_time = now
    return _jwks_client


def validate_cognito_token(token: str) -> dict | None:
    """Validate Cognito JWT and return claims (sub, email, etc.)."""
    try:
        jwks = get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)
        # Cognito access tokens don't have 'aud' claim, they have 'client_id'
        # So we must skip audience verification for access tokens
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
            options={"verify_aud": False},
        )
        # Verify client_id is one of ours
        client_id = claims.get("client_id", claims.get("aud", ""))
        if client_id not in [COGNITO_APP_CLIENT_ID, COGNITO_LOGIN_CLIENT_ID]:
            logger.warning("Token from unknown client", extra={"client_id": client_id})
            return None
        return claims
    except Exception as e:
        logger.warning("JWT validation failed", extra={"error": str(e)})
        return None


# =============================================================================
# SECRETS MANAGER (Token PipeRun por usuário)
# =============================================================================

def get_piperun_token(cognito_sub: str) -> str | None:
    """Retrieve user's PipeRun token from Secrets Manager."""
    secret_id = f"{SECRETS_PREFIX}/{cognito_sub}"
    try:
        response = secrets_client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response["SecretString"])
        return secret.get("piperun_token")
    except secrets_client.exceptions.ResourceNotFoundException:
        logger.info("No PipeRun token found", extra={"sub": cognito_sub})
        return None
    except Exception as e:
        logger.error("Error retrieving secret", extra={"error": str(e), "sub": cognito_sub})
        return None


def store_piperun_token(cognito_sub: str, piperun_token: str, user_email: str):
    """Store user's PipeRun token in Secrets Manager."""
    secret_id = f"{SECRETS_PREFIX}/{cognito_sub}"
    secret_value = json.dumps({
        "piperun_token": piperun_token,
        "user_email": user_email,
        "registered_at": int(time.time()),
    })
    try:
        secrets_client.create_secret(
            Name=secret_id,
            SecretString=secret_value,
            Description=f"PipeRun token for {user_email}",
        )
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.put_secret_value(
            SecretId=secret_id,
            SecretString=secret_value,
        )


# =============================================================================
# PIPERUN API CLIENT
# =============================================================================

@tracer.capture_method
def piperun_request(method: str, endpoint: str, token: str, params: dict = None, body: dict = None) -> dict:
    """Make authenticated request to PipeRun API."""
    url = f"{PIPERUN_BASE_URL}/{endpoint}"
    headers = {"Token": token, "Accept": "application/json", "Content-Type": "application/json"}

    if method == "GET":
        response = requests.get(url, headers=headers, params=params, timeout=30)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=body, timeout=30)
    elif method == "PUT":
        response = requests.put(url, headers=headers, json=body, timeout=30)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers, timeout=30)
    else:
        raise ValueError(f"Unsupported method: {method}")

    if response.status_code == 401:
        raise PipeRunAuthError("Token PipeRun expirado ou inválido")

    response.raise_for_status()
    return response.json()


class PipeRunAuthError(Exception):
    """Raised when PipeRun returns 401 (token expired/invalid)."""
    pass


# =============================================================================
# TOOLS — LEITURA
# =============================================================================

def tool_piperun_listar_funis(params: dict, token: str) -> dict:
    """Lista funis e etapas disponíveis."""
    return piperun_request("GET", "pipelines", token)


def tool_piperun_listar_deals(params: dict, token: str) -> dict:
    """Lista negócios filtrando por funil, etapa, responsável, status e origem."""
    qp = {}
    for k in ("pipeline_id", "stage_id", "owner_id", "status", "origin_id", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_request("GET", "deals", token, params=qp)


def tool_piperun_obter_deal(params: dict, token: str) -> dict:
    """Retorna detalhes completos de um deal por ID."""
    return piperun_request("GET", f"deals/{params['deal_id']}", token)


def tool_piperun_buscar_contatos(params: dict, token: str) -> dict:
    """Busca pessoas e empresas por nome, e-mail, CNPJ ou telefone."""
    qp = {}
    for k in ("name", "email", "cpf_cnpj", "phone", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_request("GET", "persons", token, params=qp)


def tool_piperun_obter_contato(params: dict, token: str) -> dict:
    """Detalhes completos de um contato."""
    return piperun_request("GET", f"persons/{params['person_id']}", token)


def tool_piperun_listar_atividades(params: dict, token: str) -> dict:
    """Lista atividades por usuário ou deal, com filtro de atraso."""
    qp = {}
    for k in ("deal_id", "user_id", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_request("GET", "activities", token, params=qp)


def tool_piperun_listar_propostas(params: dict, token: str) -> dict:
    """Lista propostas vinculadas a um deal."""
    qp = {}
    for k in ("deal_id", "page"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_request("GET", "proposals", token, params=qp)


def tool_piperun_listar_origens(params: dict, token: str) -> dict:
    """Lista todas as origens (sources) disponíveis no PipeRun."""
    return piperun_request("GET", "sources", token)


# =============================================================================
# TOOLS — ESCRITA
# =============================================================================

def tool_piperun_criar_deal(params: dict, token: str) -> dict:
    """Cria novo negócio em um funil e etapa especificados."""
    body = {}
    for k in ("title", "pipeline_id", "stage_id", "value", "user_id", "person_id", "company_id", "custom_fields"):
        if params.get(k) is not None:
            body[k] = params[k]
    return piperun_request("POST", "deals", token, body=body)


def tool_piperun_atualizar_deal(params: dict, token: str) -> dict:
    """Atualiza campos de um deal existente."""
    deal_id = params.pop("deal_id")
    body = {}
    for k in ("title", "value", "user_id", "freebusy", "custom_fields"):
        if params.get(k) is not None:
            body[k] = params[k]
    return piperun_request("PUT", f"deals/{deal_id}", token, body=body)


def tool_piperun_mover_etapa(params: dict, token: str) -> dict:
    """Move um deal entre etapas do mesmo funil."""
    deal_id = params["deal_id"]
    body = {"stage_id": params["stage_id"]}
    return piperun_request("PUT", f"deals/{deal_id}", token, body=body)


def tool_piperun_criar_atividade(params: dict, token: str) -> dict:
    """Cria atividade (ligação, reunião, tarefa) atrelada a deal ou contato."""
    body = {}
    for k in ("deal_id", "person_id", "type", "title", "description", "due_date", "user_id"):
        if params.get(k) is not None:
            body[k] = params[k]
    return piperun_request("POST", "activities", token, body=body)


def tool_piperun_concluir_atividade(params: dict, token: str) -> dict:
    """Marca atividade como concluída com nota opcional."""
    activity_id = params["activity_id"]
    body = {"done": True}
    if params.get("note"):
        body["note"] = params["note"]
    return piperun_request("PUT", f"activities/{activity_id}", token, body=body)


def tool_piperun_criar_nota(params: dict, token: str) -> dict:
    """Adiciona nota textual em um deal ou contato."""
    body = {}
    for k in ("deal_id", "person_id", "content"):
        if params.get(k) is not None:
            body[k] = params[k]
    return piperun_request("POST", "notes", token, body=body)


def tool_piperun_criar_proposta(params: dict, token: str) -> dict:
    """Cria proposta comercial atrelada a um deal."""
    body = {}
    for k in ("deal_id", "title", "value", "items"):
        if params.get(k) is not None:
            body[k] = params[k]
    return piperun_request("POST", "proposals", token, body=body)


def tool_piperun_excluir_deal(params: dict, token: str) -> dict:
    """Exclui (deleta) uma oportunidade/deal pelo ID."""
    deal_id = params["deal_id"]
    return piperun_request("DELETE", f"deals/{deal_id}", token)


# =============================================================================
# TOOLS REGISTRY
# =============================================================================

TOOLS = {
    "piperun_listar_funis": tool_piperun_listar_funis,
    "piperun_listar_deals": tool_piperun_listar_deals,
    "piperun_obter_deal": tool_piperun_obter_deal,
    "piperun_buscar_contatos": tool_piperun_buscar_contatos,
    "piperun_obter_contato": tool_piperun_obter_contato,
    "piperun_listar_atividades": tool_piperun_listar_atividades,
    "piperun_listar_propostas": tool_piperun_listar_propostas,
    "piperun_listar_origens": tool_piperun_listar_origens,
    "piperun_criar_deal": tool_piperun_criar_deal,
    "piperun_atualizar_deal": tool_piperun_atualizar_deal,
    "piperun_mover_etapa": tool_piperun_mover_etapa,
    "piperun_criar_atividade": tool_piperun_criar_atividade,
    "piperun_concluir_atividade": tool_piperun_concluir_atividade,
    "piperun_criar_nota": tool_piperun_criar_nota,
    "piperun_criar_proposta": tool_piperun_criar_proposta,
    "piperun_excluir_deal": tool_piperun_excluir_deal,
}


MCP_TOOLS_SCHEMA = [
    {
        "name": "piperun_listar_funis",
        "description": "Lista funis de vendas e suas etapas disponíveis no PipeRun da DATI.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_listar_deals",
        "description": "Lista negócios (deals) filtrando por funil, etapa, responsável, status e origem.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "integer", "description": "ID do funil"},
                "stage_id": {"type": "integer", "description": "ID da etapa"},
                "owner_id": {"type": "integer", "description": "ID do responsável"},
                "status": {"type": "string", "enum": ["open", "won", "lost"]},
                "origin_id": {"type": "integer", "description": "ID da origem (source). Use piperun_listar_origens para ver as disponíveis."},
                "page": {"type": "integer"},
                "show": {"type": "integer", "description": "Registros por página (max 200)"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_obter_deal",
        "description": "Retorna detalhes completos de um negócio pelo ID, incluindo campos customizados.",
        "inputSchema": {
            "type": "object",
            "required": ["deal_id"],
            "properties": {"deal_id": {"type": "integer", "description": "ID numérico do deal"}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_buscar_contatos",
        "description": "Busca pessoas e empresas por nome, e-mail, CNPJ ou telefone.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "cpf_cnpj": {"type": "string"},
                "phone": {"type": "string"},
                "page": {"type": "integer"},
                "show": {"type": "integer"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_obter_contato",
        "description": "Detalhes completos de um contato (pessoa).",
        "inputSchema": {
            "type": "object",
            "required": ["person_id"],
            "properties": {"person_id": {"type": "integer"}},
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_listar_atividades",
        "description": "Lista atividades por usuário ou deal, com filtro de atraso.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "integer"},
                "user_id": {"type": "integer"},
                "page": {"type": "integer"},
                "show": {"type": "integer"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_listar_propostas",
        "description": "Lista propostas vinculadas a um deal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "integer"},
                "page": {"type": "integer"},
            },
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_listar_origens",
        "description": "Lista todas as origens (sources) disponíveis no PipeRun. Use para obter IDs de origem para filtrar deals.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "piperun_criar_deal",
        "description": "Cria novo negócio em um funil e etapa especificados.",
        "inputSchema": {
            "type": "object",
            "required": ["title", "pipeline_id", "stage_id"],
            "properties": {
                "title": {"type": "string", "description": "Título do negócio"},
                "pipeline_id": {"type": "integer", "description": "ID do funil"},
                "stage_id": {"type": "integer", "description": "ID da etapa"},
                "value": {"type": "number", "description": "Valor em BRL"},
                "user_id": {"type": "integer", "description": "Responsável"},
                "person_id": {"type": "integer", "description": "Contato vinculado"},
                "company_id": {"type": "integer", "description": "Empresa vinculada"},
                "custom_fields": {"type": "object", "additionalProperties": True},
            },
        },
    },
    {
        "name": "piperun_atualizar_deal",
        "description": "Atualiza campos de um negócio existente. Não use para mover etapa.",
        "inputSchema": {
            "type": "object",
            "required": ["deal_id"],
            "properties": {
                "deal_id": {"type": "integer", "description": "ID do deal"},
                "title": {"type": "string"},
                "value": {"type": "number", "description": "Valor em BRL"},
                "user_id": {"type": "integer", "description": "Responsável"},
                "freebusy": {"type": "string"},
                "custom_fields": {"type": "object", "additionalProperties": True},
            },
        },
    },
    {
        "name": "piperun_mover_etapa",
        "description": "Move um deal entre etapas do mesmo funil.",
        "inputSchema": {
            "type": "object",
            "required": ["deal_id", "stage_id"],
            "properties": {
                "deal_id": {"type": "integer", "description": "ID do deal"},
                "stage_id": {"type": "integer", "description": "ID da nova etapa"},
            },
        },
    },
    {
        "name": "piperun_criar_atividade",
        "description": "Cria atividade (ligação, reunião, tarefa) atrelada a deal ou contato.",
        "inputSchema": {
            "type": "object",
            "required": ["title", "type"],
            "properties": {
                "deal_id": {"type": "integer"},
                "person_id": {"type": "integer"},
                "type": {"type": "string", "enum": ["call", "meeting", "task"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "due_date": {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                "user_id": {"type": "integer"},
            },
        },
    },
    {
        "name": "piperun_concluir_atividade",
        "description": "Marca atividade como concluída com nota opcional.",
        "inputSchema": {
            "type": "object",
            "required": ["activity_id"],
            "properties": {
                "activity_id": {"type": "integer"},
                "note": {"type": "string", "description": "Nota de conclusão"},
            },
        },
    },
    {
        "name": "piperun_criar_nota",
        "description": "Adiciona nota textual em um deal ou contato.",
        "inputSchema": {
            "type": "object",
            "required": ["content"],
            "properties": {
                "deal_id": {"type": "integer"},
                "person_id": {"type": "integer"},
                "content": {"type": "string", "description": "Texto da nota"},
            },
        },
    },
    {
        "name": "piperun_criar_proposta",
        "description": "Cria proposta comercial atrelada a um deal.",
        "inputSchema": {
            "type": "object",
            "required": ["deal_id", "title"],
            "properties": {
                "deal_id": {"type": "integer"},
                "title": {"type": "string"},
                "value": {"type": "number"},
                "items": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    {
        "name": "piperun_excluir_deal",
        "description": "Exclui (deleta) permanentemente uma oportunidade/deal pelo ID. Ação irreversível.",
        "inputSchema": {
            "type": "object",
            "required": ["deal_id"],
            "properties": {
                "deal_id": {"type": "integer", "description": "ID do deal a ser excluído"},
            },
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": True},
    },
]


# =============================================================================
# MCP PROTOCOL HANDLER
# =============================================================================

def handle_mcp_request(body: dict, piperun_token: str) -> dict:
    """Process MCP JSON-RPC request."""
    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mcp-piperun-cognito", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": MCP_TOOLS_SCHEMA}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Tool não encontrada: {tool_name}"},
            }

        try:
            result = TOOLS[tool_name](tool_args, piperun_token)
            summary = f"Executado {tool_name} com sucesso."
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(
                        {"summary": summary, "data": result},
                        ensure_ascii=False, default=str,
                    )}],
                    "isError": False,
                },
            }
        except PipeRunAuthError:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "code": "authentication_failed",
                        "message_user": "Seu token PipeRun expirou. Recadastre em /register-token.",
                        "message_dev": "PipeRun API returned 401",
                    })}],
                    "isError": True,
                },
            }
        except requests.exceptions.HTTPError as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "code": "piperun_error",
                        "message_user": f"Erro ao acessar PipeRun: {e.response.status_code if e.response else 'timeout'}",
                        "message_dev": e.response.text[:500] if e.response else str(e),
                    })}],
                    "isError": True,
                },
            }
        except Exception as e:
            logger.exception("Tool execution error")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "code": "internal_error",
                        "message_user": "Erro interno. Tente novamente.",
                        "message_dev": str(e),
                    })}],
                    "isError": True,
                },
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def resp_json(status: int, body: dict, extra_headers: dict = None) -> dict:
    """Build API Gateway response."""
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    return {"statusCode": status, "headers": headers, "body": json.dumps(body)}


def get_signup_page(base_url: str, cognito_base: str) -> str:
    """Return HTML page for self-service signup + token registration."""
    return SIGNUP_PAGE_HTML.replace("{API_BASE_URL}", base_url).replace(
        "{COGNITO_BASE}", cognito_base
    ).replace("{CLIENT_ID}", COGNITO_APP_CLIENT_ID).replace(
        "{USER_POOL_ID}", COGNITO_USER_POOL_ID
    ).replace("{REGION}", COGNITO_REGION)


def get_authorize_page(base_url: str, redirect_uri: str, state: str) -> str:
    """Return HTML page for OAuth authorize flow (login + token registration)."""
    from authorize_page import AUTHORIZE_PAGE_HTML
    return AUTHORIZE_PAGE_HTML.replace("{API_BASE_URL}", base_url).replace(
        "{CLIENT_ID}", COGNITO_LOGIN_CLIENT_ID
    ).replace("{REGION}", COGNITO_REGION).replace(
        "{REDIRECT_URI}", redirect_uri
    ).replace("{STATE}", state)


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: Any) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    headers = event.get("headers", {})
    auth_header = headers.get("authorization", "")

    base_url = API_BASE_URL
    cognito_base = f"https://{COGNITO_DOMAIN}.auth.{COGNITO_REGION}.amazoncognito.com"

    logger.info("Request received", extra={"method": method, "path": path})

    # =========================================================================
    # WELL-KNOWN ENDPOINTS (OAuth Discovery)
    # =========================================================================
    if path == "/.well-known/oauth-protected-resource":
        return resp_json(200, {
            "resource": f"{base_url}/mcp",
            "authorization_servers": [cognito_base],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["openid", "email", "profile"],
        })

    if path == "/.well-known/oauth-authorization-server":
        return resp_json(200, {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/authorize",
            "token_endpoint": f"{base_url}/token",
            "registration_endpoint": f"{base_url}/register",
            "jwks_uri": f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
            "scopes_supported": ["openid", "email", "profile", "piperun.read", "piperun.write"],
        })

    # =========================================================================
    # AUTHORIZE (OAuth — serve página de login/signup + token PipeRun)
    # =========================================================================
    if path == "/authorize" and method == "GET":
        qs = event.get("queryStringParameters", {}) or {}
        redirect_uri = qs.get("redirect_uri", "")
        state = qs.get("state", "")
        # Serve a página de login integrada ao fluxo OAuth
        html = get_authorize_page(base_url, redirect_uri, state)
        return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": html}

    # =========================================================================
    # TOKEN ENDPOINT (troca code por access_token)
    # =========================================================================
    if path == "/token" and method == "POST":
        import base64
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")

        # Pode vir como form-urlencoded ou JSON
        if "application/json" in headers.get("content-type", ""):
            params = json.loads(body_str)
        else:
            import urllib.parse
            params = dict(urllib.parse.parse_qsl(body_str))

        code = params.get("code", "")
        if not code:
            return resp_json(400, {"error": "invalid_request", "error_description": "code is required"})

        # O code É o access_token do Cognito (passado direto no redirect)
        claims = validate_cognito_token(code)
        if claims:
            # Verificar se tem token PipeRun cadastrado
            piperun_token = get_piperun_token(claims["sub"])
            if piperun_token:
                return resp_json(200, {
                    "access_token": code,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                })

        return resp_json(400, {"error": "invalid_grant", "error_description": "Invalid or expired code"})

    # =========================================================================
    # REGISTER (Dynamic Client Registration)
    # =========================================================================
    if path == "/register" and method == "POST":
        return resp_json(201, {
            "client_id": COGNITO_APP_CLIENT_ID,
            "client_name": "MCP PipeRun DATI",
            "redirect_uris": [],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        })

    # =========================================================================
    # REGISTER TOKEN (Cadastro do token PipeRun pelo usuário)
    # =========================================================================
    if path == "/register-token" and method == "POST":
        # Requires valid Cognito JWT
        if not auth_header.startswith("Bearer "):
            return resp_json(401, {"error": "Token Cognito obrigatório"})

        claims = validate_cognito_token(auth_header[7:])
        if not claims:
            return resp_json(401, {"error": "Token Cognito inválido ou expirado"})

        # Parse body
        import base64
        body_str = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")
        body = json.loads(body_str)

        piperun_token = body.get("piperun_token", "")
        check_only = body.get("check_only", False)

        # Check-only mode: just verify if user already has a token registered
        if check_only:
            cognito_sub = claims["sub"]
            existing = get_piperun_token(cognito_sub)
            if existing:
                return resp_json(200, {"already_registered": True})
            return resp_json(200, {"already_registered": False})

        if not piperun_token:
            return resp_json(400, {"error": "Campo piperun_token obrigatório"})

        # Validate token with PipeRun API
        try:
            me_resp = requests.get(
                f"{PIPERUN_BASE_URL}/me",
                headers={"Token": piperun_token, "Accept": "application/json"},
                timeout=10,
            )
            if not me_resp.ok:
                return resp_json(400, {
                    "error": "Token PipeRun inválido",
                    "message": "Verifique o token em https://app.pipe.run/v2/me/user-data",
                })
        except Exception as e:
            logger.warning("PipeRun validation failed", extra={"error": str(e)})
            return resp_json(502, {"error": "Não foi possível validar com PipeRun"})

        # Store in Secrets Manager
        cognito_sub = claims["sub"]
        user_email = claims.get("email", "unknown")
        store_piperun_token(cognito_sub, piperun_token, user_email)

        metrics.add_metric(name="TokenRegistered", unit=MetricUnit.Count, value=1)
        logger.info("Token registered", extra={"sub": cognito_sub, "email": user_email})

        return resp_json(200, {
            "message": "Token PipeRun cadastrado com sucesso",
            "user_email": user_email,
        })

    # =========================================================================
    # SIGNUP PAGE (self-service)
    # =========================================================================
    if path == "/signup" and method == "GET":
        html = get_signup_page(base_url, cognito_base)
        return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": html}

    # =========================================================================
    # MCP ENDPOINT
    # =========================================================================
    if path == "/mcp":
        # Require Bearer token (Cognito JWT)
        if not auth_header.startswith("Bearer "):
            return {
                "statusCode": 401,
                "headers": {
                    "WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"',
                    "Content-Type": "application/json",
                },
                "body": json.dumps({"error": "unauthorized"}),
            }

        claims = validate_cognito_token(auth_header[7:])
        if not claims:
            return {
                "statusCode": 401,
                "headers": {
                    "WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"',
                    "Content-Type": "application/json",
                },
                "body": json.dumps({"error": "invalid_token"}),
            }

        cognito_sub = claims["sub"]

        # Get PipeRun token from Secrets Manager
        piperun_token = get_piperun_token(cognito_sub)
        if not piperun_token:
            return resp_json(403, {
                "error": "piperun_token_not_found",
                "message": "Token PipeRun não cadastrado. Acesse /register-token primeiro.",
            })

        # Handle MCP request
        if method == "POST":
            import base64
            body_str = event.get("body", "{}")
            if event.get("isBase64Encoded"):
                body_str = base64.b64decode(body_str).decode("utf-8")
            body = json.loads(body_str)

            metrics.add_metric(name="MCPRequest", unit=MetricUnit.Count, value=1)
            result = handle_mcp_request(body, piperun_token)

            if result is None:
                return {"statusCode": 202, "headers": {"Content-Type": "application/json"}, "body": ""}

            accept = headers.get("accept", "")
            if "text/event-stream" in accept:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
                    "body": f"event: message\ndata: {json.dumps(result, ensure_ascii=False, default=str)}\n\n",
                }
            return resp_json(200, result)

        if method == "GET":
            accept = headers.get("accept", "")
            if "text/event-stream" in accept:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
                    "body": "event: open\ndata: {}\n\n",
                }
            return resp_json(200, {
                "jsonrpc": "2.0",
                "id": None,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "mcp-piperun-cognito", "version": "1.0.0"},
                },
            })

    return resp_json(404, {"error": "Not found"})
