"""
MCP Tiflux - Lambda Handler (READ-ONLY) com OAuth service-to-service
Proxy para a API v2 do Tiflux, exposto via API Gateway para uso como MCP Server.
O QuickSight envia client_id/secret para /token e recebe um access_token.
"""

import json
import os
import secrets
import urllib.parse
from typing import Any

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="mcp-tiflux")
tracer = Tracer(service="mcp-tiflux")
metrics = Metrics(service="mcp-tiflux", namespace="MCPTiflux")

TIFLUX_BASE_URL = os.environ.get("TIFLUX_BASE_URL", "https://api.tiflux.com/api/v2")
TIFLUX_SECRET_NAME = os.environ.get("TIFLUX_SECRET_NAME", "mcp-tiflux/api-token")
API_BASE_URL = os.environ.get("API_BASE_URL", "")

# OAuth credentials fixas para service-to-service
# O QuickSight vai usar esses valores para autenticar
OAUTH_CLIENT_ID = "mcp-tiflux-service"
OAUTH_CLIENT_SECRET = "dati-mcp-tiflux-2026"

_secrets_client = boto3.client("secretsmanager")
_cached_token = None


def get_tiflux_token() -> str:
    """Recupera o token do Tiflux do Secrets Manager via boto3."""
    global _cached_token
    if _cached_token:
        return _cached_token
    response = _secrets_client.get_secret_value(SecretId=TIFLUX_SECRET_NAME)
    secret_data = json.loads(response["SecretString"])
    _cached_token = secret_data["token"]
    return _cached_token


def tiflux_headers() -> dict:
    """Headers padrão para requests ao Tiflux."""
    return {
        "Authorization": f"Bearer {get_tiflux_token()}",
        "Accept": "application/json",
    }


@tracer.capture_method
def tiflux_get(endpoint: str, params: dict = None) -> dict:
    """GET request para a API do Tiflux."""
    url = f"{TIFLUX_BASE_URL}{endpoint}"
    logger.info("Tiflux GET", extra={"url": url, "params": params})
    response = requests.get(url, headers=tiflux_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# =============================================================================
# TOOLS - Apenas operações de leitura (GET/LIST)
# =============================================================================


def tool_list_tickets(params: dict) -> dict:
    """Listar tickets com filtros opcionais."""
    query_params = {"limit": 200}
    if params.get("search"):
        query_params["search"] = params["search"]
    if params.get("client_id"):
        query_params["client_id"] = params["client_id"]
    if params.get("desk_id"):
        query_params["desk_id"] = params["desk_id"]
    if params.get("responsible_id"):
        query_params["responsible_id"] = params["responsible_id"]
    if params.get("priority_id"):
        query_params["priority_id"] = params["priority_id"]
    if params.get("stage_id"):
        query_params["stage_id"] = params["stage_id"]
    if params.get("status_id"):
        query_params["status_id"] = params["status_id"]
    if "is_closed" in params:
        query_params["is_closed"] = str(params["is_closed"]).lower()

    data = tiflux_get("/tickets", params=query_params)
    if isinstance(data, list):
        return [
            {
                "ticket_number": t.get("ticket_number"),
                "title": t.get("title"),
                "client": t.get("client", {}).get("name") if t.get("client") else None,
                "desk": t.get("desk", {}).get("name") if t.get("desk") else None,
                "status": t.get("status", {}).get("name") if t.get("status") else None,
                "stage": t.get("stage", {}).get("name") if t.get("stage") else None,
                "priority": t.get("priority", {}).get("name") if t.get("priority") else None,
                "responsible": t.get("responsible", {}).get("name", "Unassigned") if t.get("responsible") else "Unassigned",
                "created_at": t.get("created_at"),
                "is_closed": t.get("is_closed"),
            }
            for t in data
        ]
    return data


def tool_get_ticket(params: dict) -> dict:
    """Ver detalhes de um ticket por número ou buscar por texto."""
    if params.get("ticket_number"):
        return tiflux_get(f"/tickets/{params['ticket_number']}")
    # Busca por texto usando o parâmetro search nativo da API
    search_term = params.get("search", "")
    if search_term:
        data = tiflux_get("/tickets", params={"search": search_term, "limit": 200})
        if isinstance(data, list):
            return [
                {
                    "ticket_number": t.get("ticket_number"),
                    "title": t.get("title"),
                    "client": t.get("client", {}).get("name") if t.get("client") else None,
                    "desk": t.get("desk", {}).get("name") if t.get("desk") else None,
                    "status": t.get("status", {}).get("name") if t.get("status") else None,
                    "responsible": t.get("responsible", {}).get("name", "Unassigned") if t.get("responsible") else "Unassigned",
                    "created_at": t.get("created_at"),
                }
                for t in data
            ]
        return data
    return {"error": "Informe ticket_number ou search"}


def tool_list_clients(params: dict) -> dict:
    """Listar clientes com filtros opcionais."""
    query_params = {"limit": 200}
    if params.get("name"):
        query_params["name"] = params["name"]
    if "status" in params:
        query_params["status"] = params["status"]

    data = tiflux_get("/clients", params=query_params)
    if isinstance(data, list):
        return [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "social": c.get("social"),
                "social_revenue": c.get("social_revenue"),
                "status": c.get("status"),
            }
            for c in data
        ]
    return data


def tool_get_client(params: dict) -> dict:
    """Ver detalhes de um cliente por ID ou buscar por nome."""
    if params.get("client_id"):
        return tiflux_get(f"/clients/{params['client_id']}")
    # Busca por nome usando o parâmetro name nativo da API (busca parcial)
    name_filter = params.get("name", "")
    if name_filter:
        data = tiflux_get("/clients", params={"name": name_filter, "limit": 200})
        if isinstance(data, list):
            return [{"id": c.get("id"), "name": c.get("name"), "social": c.get("social"), "status": c.get("status")} for c in data]
        return data
    return {"error": "Informe client_id ou name"}


def tool_list_desks(params: dict) -> dict:
    """Listar mesas de serviço (desks) do Tiflux."""
    return tiflux_get("/desks", params={"limit": 200})


def tool_get_ticket_appointments(params: dict) -> dict:
    """Listar apontamentos de horas de um ticket."""
    ticket_number = params["ticket_number"]
    return tiflux_get(f"/tickets/{ticket_number}/appointments", params={"limit": 200})


# =============================================================================
# ROUTER - Apenas tools de leitura
# =============================================================================

TOOLS = {
    "list_tickets": tool_list_tickets,
    "get_ticket": tool_get_ticket,
    "list_clients": tool_list_clients,
    "get_client": tool_get_client,
    "list_desks": tool_list_desks,
    "get_ticket_appointments": tool_get_ticket_appointments,
}


# =============================================================================
# MCP PROTOCOL - Implementação do protocolo MCP (JSON-RPC 2.0)
# =============================================================================

MCP_TOOLS_SCHEMA = [
    {
        "name": "list_tickets",
        "description": "Listar tickets do Tiflux com filtros opcionais. Retorna resumo com número, título, cliente, mesa, status, etapa, prioridade, responsável e data de criação.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Busca textual por título ou conteúdo do ticket"},
                "client_id": {"type": "integer", "description": "Filtrar por ID do cliente"},
                "desk_id": {"type": "integer", "description": "Filtrar por ID da mesa de serviço"},
                "responsible_id": {"type": "integer", "description": "Filtrar por ID do responsável"},
                "priority_id": {"type": "integer", "description": "Filtrar por ID da prioridade"},
                "stage_id": {"type": "integer", "description": "Filtrar por ID da etapa"},
                "status_id": {"type": "integer", "description": "Filtrar por ID do status"},
                "is_closed": {"type": "boolean", "description": "Filtrar por tickets fechados (true) ou abertos (false)"},
            },
        },
    },
    {
        "name": "get_ticket",
        "description": "Ver detalhes completos de um ticket pelo número, ou buscar tickets por texto (pesquisa parcial no título e conteúdo).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_number": {"type": "integer", "description": "Número do ticket (retorna detalhes completos)"},
                "search": {"type": "string", "description": "Texto para buscar tickets (pesquisa parcial no título/conteúdo)"},
            },
        },
    },
    {
        "name": "list_clients",
        "description": "Listar clientes do Tiflux com filtros opcionais por nome e status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Buscar clientes por nome (pesquisa parcial, ex: 'celk' encontra 'Celk Sistemas')"},
                "status": {"type": "boolean", "description": "Filtrar por status: true (ativos) ou false (inativos)"},
            },
        },
    },
    {
        "name": "get_client",
        "description": "Ver detalhes completos de um cliente pelo ID, ou buscar clientes por nome (pesquisa parcial).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "integer", "description": "ID do cliente (retorna detalhes completos)"},
                "name": {"type": "string", "description": "Nome ou parte do nome para buscar clientes (ex: 'celk' encontra 'Celk Sistemas')"},
            },
        },
    },
    {
        "name": "list_desks",
        "description": "Listar todas as mesas de serviço (filas de atendimento) do Tiflux. Útil para obter desk_id para filtrar tickets.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_ticket_appointments",
        "description": "Listar apontamentos de horas de um ticket. Retorna data, horário início/fim, descrição, usuário responsável e valorização.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_number": {"type": "integer", "description": "Número do ticket"},
            },
            "required": ["ticket_number"],
        },
    },
]


def handle_mcp_request(body: dict) -> dict:
    """Processa uma requisição MCP (JSON-RPC 2.0)."""
    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params", {})

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "mcp-tiflux",
                    "version": "1.1.0",
                },
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": MCP_TOOLS_SCHEMA},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
            }

        try:
            result = TOOLS[tool_name](tool_args)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
                    "isError": False,
                },
            }
        except requests.exceptions.HTTPError as e:
            error_body = e.response.text if e.response else str(e)
            logger.error("Tiflux API error", extra={"tool": tool_name, "error": error_body})
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Erro na API Tiflux: {error_body}"}],
                    "isError": True,
                },
            }
        except Exception as e:
            logger.exception("Tool execution error", extra={"tool": tool_name})
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Erro interno: {str(e)}"}],
                    "isError": True,
                },
            }

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


# =============================================================================
# HELPERS
# =============================================================================


def resp_json(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


# =============================================================================
# LAMBDA HANDLER
# =============================================================================


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: Any) -> dict:
    """Lambda handler — roteia entre MCP, OAuth e metadata endpoints."""
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    headers = event.get("headers", {})
    auth_header = headers.get("authorization", "")
    accept_header = headers.get("accept", "")

    base_url = API_BASE_URL or f"https://{event['requestContext']['domainName']}"

    logger.info("Request", extra={"method": method, "path": path})

    # =========================================================================
    # WELL-KNOWN METADATA
    # =========================================================================
    if path == "/.well-known/oauth-protected-resource":
        return resp_json(200, {"resource": base_url + "/mcp", "authorization_servers": [base_url], "bearer_methods_supported": ["header"]})

    if path == "/.well-known/oauth-authorization-server":
        return resp_json(200, {
            "issuer": base_url,
            "authorization_endpoint": base_url + "/mcp",
            "token_endpoint": base_url + "/token",
            "registration_endpoint": base_url + "/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["client_credentials"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        })

    # Discovery paths extras que o QuickSight tenta
    if path in ("/.well-known/openid-configuration", "/token/.well-known/openid-configuration", "/.well-known/oauth-protected-resource/token"):
        return resp_json(200, {
            "issuer": base_url,
            "token_endpoint": base_url + "/token",
            "authorization_endpoint": base_url + "/mcp",
            "grant_types_supported": ["client_credentials"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        })

    # =========================================================================
    # TOKEN ENDPOINT (client_credentials) — sem Bearer token
    # =========================================================================
    if path == "/token" and method == "POST" and not auth_header.startswith("Bearer "):
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            import base64
            body_str = base64.b64decode(body_str).decode("utf-8")

        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            params = json.loads(body_str) if body_str else {}
        else:
            params = dict(urllib.parse.parse_qsl(body_str)) if body_str else {}

        grant_type = params.get("grant_type", "")
        client_id = params.get("client_id", "")
        client_secret = params.get("client_secret", "")

        # Suportar Basic Auth (QuickSight envia credenciais assim)
        if not client_id and auth_header.startswith("Basic "):
            import base64 as b64
            decoded = b64.b64decode(auth_header[6:]).decode("utf-8")
            if ":" in decoded:
                client_id, client_secret = decoded.split(":", 1)

        logger.info("Token request", extra={"grant_type": grant_type, "client_id": client_id})

        # Validar credenciais
        if client_id != OAUTH_CLIENT_ID or client_secret != OAUTH_CLIENT_SECRET:
            return resp_json(401, {"error": "invalid_client", "error_description": "Invalid client credentials"})

        # Gerar access token
        access_token = secrets.token_urlsafe(48)
        return resp_json(200, {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400,
        })

    # GET /token — discovery
    if path == "/token" and method == "GET" and not auth_header.startswith("Bearer "):
        return resp_json(200, {"token_endpoint": base_url + "/token"})

    # =========================================================================
    # REGISTER ENDPOINT
    # =========================================================================
    if path == "/register" and method == "POST":
        return resp_json(201, {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "client_name": "MCP Tiflux",
            "grant_types": ["client_credentials"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })

    # =========================================================================
    # /mcp, /, /token, /token/sse ENDPOINT — MCP requests com Bearer
    # =========================================================================
    if path in ("/mcp", "/", "/token", "/token/sse"):

        # With Bearer → MCP request
        if auth_header.startswith("Bearer "):
            if method == "POST":
                body_str = event.get("body", "{}")
                if event.get("isBase64Encoded"):
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8")
                body = json.loads(body_str) if isinstance(body_str, str) else body_str

                result = handle_mcp_request(body)
                if result is None:
                    return {"statusCode": 202, "headers": {"Content-Type": "application/json"}, "body": ""}

                if "text/event-stream" in accept_header:
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": f"event: message\ndata: {json.dumps(result, ensure_ascii=False, default=str)}\n\n"}

                return resp_json(200, result)

            if method == "GET":
                if "text/event-stream" in accept_header:
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": "event: open\ndata: {}\n\n"}
                return resp_json(200, {"jsonrpc": "2.0", "id": None, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-tiflux", "version": "1.1.0"}}})

        # Without Bearer — OAuth authorize or 401
        if method == "GET":
            qs = event.get("queryStringParameters", {}) or {}
            if qs.get("response_type") == "code":
                redirect_uri = qs.get("redirect_uri", "")
                state = qs.get("state", "")
                code = secrets.token_urlsafe(32)
                if redirect_uri:
                    sep = "&" if "?" in redirect_uri else "?"
                    return {"statusCode": 302, "headers": {"Location": f"{redirect_uri}{sep}code={code}&state={state}"}, "body": ""}

        # 401
        return {"statusCode": 401, "headers": {"WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"', "Content-Type": "application/json"}, "body": json.dumps({"error": "unauthorized"})}

    return resp_json(404, {"error": "Not found"})
