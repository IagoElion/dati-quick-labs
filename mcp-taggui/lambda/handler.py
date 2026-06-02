"""
MCP Taggui - Lambda Handler com Function URL
Suporta SSE (Server-Sent Events) para MCP Streamable HTTP transport.
OAuth 2.0 flow para QuickSight: redireciona para página de login TagguiRH,
usuário insere seu token, e o QuickSight recebe access_token via callback.
"""

import json
import os
import hashlib
import secrets
import time
import urllib.parse
import base64
from typing import Any

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="mcp-taggui")
tracer = Tracer(service="mcp-taggui")
metrics = Metrics(service="mcp-taggui", namespace="MCPTaggui")

# Config
TAGGUI_API_BASE = "https://api.tagguirh.com.br"

# Environment
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "mcp-taggui-tokens")
API_BASE_URL = os.environ.get("API_BASE_URL", "")

# AWS clients
dynamodb = boto3.resource("dynamodb")


def get_tokens_table():
    return dynamodb.Table(DYNAMODB_TABLE)


# =============================================================================
# TOKEN STORAGE (DynamoDB)
# =============================================================================

def store_token(mcp_token: str, taggui_token: str):
    """Armazena mapeamento token MCP -> token TagguiRH."""
    table = get_tokens_table()
    token_hash = hashlib.sha256(mcp_token.encode()).hexdigest()
    table.put_item(Item={
        "token_hash": token_hash,
        "taggui_token": taggui_token,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 86400 * 365,
    })


def get_taggui_token(mcp_token: str) -> str | None:
    """Recupera token TagguiRH a partir do token MCP."""
    table = get_tokens_table()
    token_hash = hashlib.sha256(mcp_token.encode()).hexdigest()
    response = table.get_item(Key={"token_hash": token_hash})
    item = response.get("Item")
    if item:
        return item.get("taggui_token")
    return None


def store_auth_state(state: str, data: dict):
    """Armazena state do OAuth flow (redirect_uri, code_challenge)."""
    table = get_tokens_table()
    table.put_item(Item={
        "token_hash": f"state:{state}",
        "redirect_uri": data.get("redirect_uri", ""),
        "code_challenge": data.get("code_challenge", ""),
        "expires_at": int(time.time()) + 600,
    })


def get_auth_state(state: str) -> dict | None:
    table = get_tokens_table()
    response = table.get_item(Key={"token_hash": f"state:{state}"})
    return response.get("Item")


def store_auth_code(code: str, taggui_token: str, redirect_uri: str):
    """Armazena code temporário que será trocado por access_token."""
    table = get_tokens_table()
    table.put_item(Item={
        "token_hash": f"code:{code}",
        "taggui_token": taggui_token,
        "redirect_uri": redirect_uri,
        "expires_at": int(time.time()) + 300,
    })


def get_auth_code(code: str) -> dict | None:
    table = get_tokens_table()
    response = table.get_item(Key={"token_hash": f"code:{code}"})
    item = response.get("Item")
    if item and item.get("expires_at", 0) > time.time():
        # Delete after use (one-time code)
        table.delete_item(Key={"token_hash": f"code:{code}"})
        return item
    return None


# =============================================================================
# TAGGUI API
# =============================================================================

def taggui_get(endpoint: str, token: str, params: dict = None) -> dict:
    url = f"{TAGGUI_API_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def taggui_post(endpoint: str, token: str, body: dict) -> dict:
    url = f"{TAGGUI_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


def taggui_patch(endpoint: str, token: str, body: dict) -> dict:
    url = f"{TAGGUI_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.patch(url, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


def validate_taggui_token(token: str) -> bool:
    """Valida token fazendo chamada de teste à API TagguiRH."""
    try:
        resp = requests.get(
            f"{TAGGUI_API_BASE}/v1/colaboradores",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 1},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


# =============================================================================
# MCP TOOLS
# =============================================================================

def tool_list_colaboradores(params: dict, token: str) -> dict:
    query = {}
    if params.get("status"):
        query["status"] = params["status"]
    query["limit"] = params.get("limit", 20)
    query["offset"] = params.get("offset", 0)
    return taggui_get("/v1/colaboradores", token, params=query)


def tool_create_colaborador(params: dict, token: str) -> dict:
    body = {k: v for k, v in params.items() if v is not None and v != ""}
    return taggui_post("/v1/colaboradores", token, body)


def tool_update_colaborador(params: dict, token: str) -> dict:
    colab_id = params.pop("id")
    body = {k: v for k, v in params.items() if v is not None and v != ""}
    return taggui_patch(f"/v1/colaboradores/{colab_id}", token, body)


def tool_list_cargos(params: dict, token: str) -> dict:
    query = {}
    if params.get("q"):
        query["q"] = params["q"]
    query["limit"] = params.get("limit", 50)
    query["offset"] = params.get("offset", 0)
    return taggui_get("/v1/cargos", token, params=query)


def tool_list_departamentos(params: dict, token: str) -> dict:
    query = {}
    if params.get("q"):
        query["q"] = params["q"]
    query["limit"] = params.get("limit", 50)
    query["offset"] = params.get("offset", 0)
    return taggui_get("/v1/departamentos", token, params=query)


def tool_list_equipes_ponto(params: dict, token: str) -> dict:
    return taggui_get("/v1/integracao/ponto/equipes", token)


def tool_list_batidas_ponto(params: dict, token: str) -> dict:
    query = {"inicio": params["inicio"], "fim": params["fim"]}
    if params.get("page") is not None:
        query["page"] = params["page"]
    if params.get("size"):
        query["size"] = params["size"]
    if params.get("sort"):
        query["sort"] = params["sort"]
    return taggui_get("/v1/integracao/ponto/batidas", token, params=query)


TOOLS = {
    "list_colaboradores": tool_list_colaboradores,
    "create_colaborador": tool_create_colaborador,
    "update_colaborador": tool_update_colaborador,
    "list_cargos": tool_list_cargos,
    "list_departamentos": tool_list_departamentos,
    "list_equipes_ponto": tool_list_equipes_ponto,
    "list_batidas_ponto": tool_list_batidas_ponto,
}


MCP_TOOLS_SCHEMA = [
    {"name": "list_colaboradores", "description": "Lista colaboradores da empresa. Filtra por status (Ativo, Inativo, Desligado, Afastado, Férias) e suporta paginação.", "inputSchema": {"type": "object", "properties": {"status": {"type": "string", "description": "Filtrar por status: Ativo, Inativo, Desligado, Afastado, Férias"}, "limit": {"type": "integer", "description": "Registros por página (1-100, padrão 20)"}, "offset": {"type": "integer", "description": "Deslocamento para paginação (padrão 0)"}}}},
    {"name": "create_colaborador", "description": "Cadastra novo colaborador. Obrigatório: nome e cpf. Cargos/departamentos devem existir (use list_cargos/list_departamentos).", "inputSchema": {"type": "object", "properties": {"nome": {"type": "string", "description": "Nome completo (obrigatório)"}, "cpf": {"type": "string", "description": "CPF com 11 dígitos (obrigatório)"}, "email_profissional": {"type": "string"}, "status": {"type": "string"}, "tipo_vinculo": {"type": "string"}, "data_entrada": {"type": "string"}, "data_saida": {"type": "string"}, "cargo_codigo": {"type": "string"}, "departamento_codigo": {"type": "string"}, "filial_codigo": {"type": "string"}, "responsavel": {"type": "object"}}, "required": ["nome", "cpf"]}},
    {"name": "update_colaborador", "description": "Atualiza dados de um colaborador pelo ID. CPF não pode ser alterado.", "inputSchema": {"type": "object", "properties": {"id": {"type": "string", "description": "ID do colaborador (obrigatório)"}, "nome": {"type": "string"}, "email_profissional": {"type": "string"}, "status": {"type": "string"}, "tipo_vinculo": {"type": "string"}, "data_entrada": {"type": "string"}, "data_saida": {"type": "string"}, "cargo_codigo": {"type": "string"}, "departamento_codigo": {"type": "string"}, "filial_codigo": {"type": "string"}, "responsavel": {"type": "object"}}, "required": ["id"]}},
    {"name": "list_cargos", "description": "Lista cargos cadastrados. Use o 'id' retornado como cargo_codigo.", "inputSchema": {"type": "object", "properties": {"q": {"type": "string", "description": "Busca parcial"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}}},
    {"name": "list_departamentos", "description": "Lista departamentos. Use o 'id' retornado como departamento_codigo.", "inputSchema": {"type": "object", "properties": {"q": {"type": "string", "description": "Busca parcial"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}}},
    {"name": "list_equipes_ponto", "description": "Lista equipes do sistema de Ponto.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_batidas_ponto", "description": "Lista batidas de ponto por período.", "inputSchema": {"type": "object", "properties": {"inicio": {"type": "string", "description": "Data inicial YYYY-MM-DD (obrigatório)"}, "fim": {"type": "string", "description": "Data final YYYY-MM-DD (obrigatório)"}, "page": {"type": "integer"}, "size": {"type": "integer"}, "sort": {"type": "string"}}, "required": ["inicio", "fim"]}},
]


# =============================================================================
# MCP PROTOCOL
# =============================================================================

def handle_mcp_request(body: dict, taggui_token: str) -> dict:
    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "mcp-taggui", "version": "1.0.0"},
        }}
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": MCP_TOOLS_SCHEMA}}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}
        try:
            result = TOOLS[tool_name](tool_args, taggui_token)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}], "isError": False}}
        except requests.HTTPError as e:
            error_body = e.response.text if e.response else str(e)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro API TagguiRH: {error_body}"}], "isError": True}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro: {str(e)}"}], "isError": True}}
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


# =============================================================================
# LOGIN PAGE HTML — página onde o usuário insere o token TagguiRH
# =============================================================================

def build_login_page(state: str, redirect_uri: str, base_url: str, error_msg: str = "") -> str:
    error_html = f'<div class="error">{error_msg}</div>' if error_msg else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TagguiRH - Autorizar MCP</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
        .container {{ background: white; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); padding: 40px; max-width: 480px; width: 90%; }}
        .logo {{ text-align: center; margin-bottom: 24px; font-size: 28px; font-weight: 700; color: #1a1a2e; }}
        .logo span {{ color: #6c63ff; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 32px; font-size: 14px; line-height: 1.5; }}
        label {{ display: block; font-weight: 600; margin-bottom: 8px; color: #333; font-size: 14px; }}
        input[type="text"] {{ width: 100%; padding: 12px 16px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; font-family: monospace; }}
        input[type="text"]:focus {{ outline: none; border-color: #6c63ff; }}
        .btn {{ width: 100%; padding: 14px; background: #6c63ff; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 20px; transition: background 0.2s; }}
        .btn:hover {{ background: #5a52d5; }}
        .help {{ text-align: center; margin-top: 16px; font-size: 12px; color: #999; }}
        .error {{ background: #fee; border: 1px solid #fcc; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Taggui<span>RH</span></div>
        <p class="subtitle">Autorize o acesso aos dados de RH da sua empresa.<br>Insira o token de API gerado no painel TagguiRH.</p>
        {error_html}
        <form method="POST" action="{base_url}/authorize-submit">
            <input type="hidden" name="state" value="{state}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <label for="token">Token de API</label>
            <input type="text" id="token" name="taggui_token" placeholder="sk_taggui_..." required>
            <button type="submit" class="btn">Autorizar</button>
        </form>
        <p class="help">Gere seu token em TagguiRH &rarr; Configurações &rarr; Chaves de API</p>
    </div>
</body>
</html>"""


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: Any) -> dict:
    """Lambda handler — single function handling all routes."""
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    headers = event.get("headers", {})
    auth_header = headers.get("authorization", "")
    accept_header = headers.get("accept", "")
    qs = event.get("queryStringParameters", {}) or {}

    logger.info("Request", extra={"method": method, "path": path})

    base_url = API_BASE_URL or f"https://{event['requestContext']['domainName']}"

    # =========================================================================
    # WELL-KNOWN METADATA
    # =========================================================================
    if path == "/.well-known/oauth-protected-resource":
        return resp_json(200, {
            "resource": base_url + "/mcp",
            "authorization_servers": [base_url],
            "bearer_methods_supported": ["header"],
        })

    if path == "/.well-known/oauth-authorization-server":
        return resp_json(200, {
            "issuer": base_url,
            "authorization_endpoint": base_url + "/authorize",
            "token_endpoint": base_url + "/token",
            "registration_endpoint": base_url + "/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        })

    # =========================================================================
    # REGISTER ENDPOINT
    # =========================================================================
    if path == "/register" and method == "POST":
        body_str = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")
        client_metadata = json.loads(body_str)
        return resp_json(201, {
            "client_id": "mcp-taggui-client",
            "client_secret": "mcp-taggui-secret",
            "client_name": client_metadata.get("client_name", "MCP Taggui Client"),
            "redirect_uris": client_metadata.get("redirect_uris", []),
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })

    # =========================================================================
    # AUTHORIZE ENDPOINT — mostra página de login TagguiRH
    # =========================================================================
    if path == "/authorize" and method == "GET":
        state = qs.get("state", secrets.token_urlsafe(32))
        redirect_uri = qs.get("redirect_uri", "")
        code_challenge = qs.get("code_challenge", "")

        # Salva state para validar depois
        store_auth_state(state, {
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
        })

        # Mostra página de login
        html = build_login_page(state, redirect_uri, base_url)
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": html,
        }

    # =========================================================================
    # AUTHORIZE SUBMIT — recebe token do form, valida, redireciona com code
    # =========================================================================
    if path == "/authorize-submit" and method == "POST":
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")
        form_data = dict(urllib.parse.parse_qsl(body_str))

        state = form_data.get("state", "")
        redirect_uri = form_data.get("redirect_uri", "")
        taggui_token = form_data.get("taggui_token", "").strip()

        if not taggui_token:
            html = build_login_page(state, redirect_uri, base_url, "Token não pode ser vazio.")
            return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": html}

        # Valida token com a API TagguiRH
        if not validate_taggui_token(taggui_token):
            html = build_login_page(state, redirect_uri, base_url, "Token inválido ou expirado. Verifique e tente novamente.")
            return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": html}

        # Gera authorization code
        code = secrets.token_urlsafe(32)
        store_auth_code(code, taggui_token, redirect_uri)

        # Redireciona de volta ao QuickSight (ou qualquer client) com o code
        if not redirect_uri:
            state_data = get_auth_state(state)
            redirect_uri = state_data.get("redirect_uri", "") if state_data else ""

        if redirect_uri:
            sep = "&" if "?" in redirect_uri else "?"
            location = f"{redirect_uri}{sep}code={code}&state={state}"
            return {"statusCode": 302, "headers": {"Location": location}, "body": ""}

        # Fallback: mostra o code na tela
        return resp_json(200, {"code": code, "state": state, "message": "Use este code no token endpoint."})

    # =========================================================================
    # TOKEN ENDPOINT — troca code por access_token
    # =========================================================================
    if path == "/token" and method == "POST":
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")

        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            params = json.loads(body_str)
        else:
            params = dict(urllib.parse.parse_qsl(body_str))

        grant_type = params.get("grant_type", "")
        code = params.get("code", "")

        logger.info("Token request", extra={"grant_type": grant_type, "has_code": bool(code)})

        if grant_type == "authorization_code" and code:
            code_data = get_auth_code(code)
            if not code_data:
                return resp_json(400, {"error": "invalid_grant", "error_description": "Code inválido ou expirado"})

            taggui_token = code_data.get("taggui_token", "")
            mcp_token = secrets.token_urlsafe(48)
            store_token(mcp_token, taggui_token)

            return resp_json(200, {
                "access_token": mcp_token,
                "token_type": "Bearer",
                "expires_in": 86400 * 365,
                "refresh_token": mcp_token,
            })

        elif grant_type == "refresh_token":
            refresh_token = params.get("refresh_token", "")
            taggui_token = get_taggui_token(refresh_token)
            if taggui_token:
                return resp_json(200, {
                    "access_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_in": 86400 * 365,
                })
            return resp_json(400, {"error": "invalid_grant"})

        return resp_json(400, {"error": "unsupported_grant_type"})

    # =========================================================================
    # /mcp ENDPOINT — MCP requests (com Bearer token)
    # =========================================================================
    if path == "/mcp":
        if auth_header.startswith("Bearer "):
            bearer_token = auth_header[7:]
            taggui_token = get_taggui_token(bearer_token)

            # Se não encontrou no DynamoDB, tenta usar direto como token TagguiRH
            if not taggui_token:
                taggui_token = bearer_token

            if method == "POST":
                body_str = event.get("body", "{}")
                if event.get("isBase64Encoded"):
                    body_str = base64.b64decode(body_str).decode("utf-8")
                body = json.loads(body_str)
                result = handle_mcp_request(body, taggui_token)

                if result is None:
                    return {"statusCode": 202, "headers": {"Content-Type": "application/json"}, "body": ""}

                if "text/event-stream" in accept_header:
                    sse_body = f"event: message\ndata: {json.dumps(result, ensure_ascii=False, default=str)}\n\n"
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": sse_body}
                return resp_json(200, result)

            if method == "GET":
                if "text/event-stream" in accept_header:
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": "event: open\ndata: {}\n\n"}
                return resp_json(200, {"jsonrpc": "2.0", "id": None, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-taggui", "version": "1.0.0"}}})

        # No Bearer — return 401
        return {
            "statusCode": 401,
            "headers": {
                "WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"',
                "Content-Type": "application/json",
            },
            "body": json.dumps({"error": "unauthorized"}),
        }

    # Fallback
    return resp_json(404, {"error": "Not found"})


# =============================================================================
# HELPERS
# =============================================================================

def resp_json(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}
