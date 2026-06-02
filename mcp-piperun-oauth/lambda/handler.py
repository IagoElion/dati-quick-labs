"""
MCP PipeRun - Lambda Handler com OAuth Proxy (token por usuário)
Cada usuário cola seu token PipeRun em uma página de login.
O QuickSight faz OAuth com nosso server, que armazena o token individual.
"""

import json
import os
import hashlib
import secrets
import time
import urllib.parse
from typing import Any

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="mcp-piperun")
tracer = Tracer(service="mcp-piperun")
metrics = Metrics(service="mcp-piperun", namespace="MCPPipeRun")

PIPERUN_BASE_URL = os.environ.get("PIPERUN_BASE_URL", "https://api.pipe.run/v1")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "mcp-piperun-tokens")
API_BASE_URL = os.environ.get("API_BASE_URL", "")

dynamodb = boto3.resource("dynamodb")
_table = None


def get_table():
    global _table
    if not _table:
        _table = dynamodb.Table(DYNAMODB_TABLE)
    return _table


def store_token(session_token: str, piperun_token: str):
    get_table().put_item(Item={
        "token_hash": hashlib.sha256(session_token.encode()).hexdigest(),
        "piperun_token": piperun_token,
        "expires_at": int(time.time()) + 86400 * 30,  # 30 dias
        "created_at": int(time.time()),
    })


def get_piperun_token(session_token: str) -> str | None:
    token_hash = hashlib.sha256(session_token.encode()).hexdigest()
    resp = get_table().get_item(Key={"token_hash": token_hash})
    item = resp.get("Item")
    if item and item.get("expires_at", 0) > time.time():
        return item.get("piperun_token")
    return None


def store_state(state: str, redirect_uri: str):
    get_table().put_item(Item={
        "token_hash": f"state:{state}",
        "redirect_uri": redirect_uri,
        "expires_at": int(time.time()) + 600,
    })


def get_state(state: str) -> dict | None:
    resp = get_table().get_item(Key={"token_hash": f"state:{state}"})
    return resp.get("Item")


# =============================================================================
# PIPERUN API (READ-ONLY)
# =============================================================================

def piperun_get(endpoint: str, token: str, params: dict = None) -> dict:
    url = f"{PIPERUN_BASE_URL}/{endpoint}"
    headers = {"token": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# =============================================================================
# TOOLS
# =============================================================================

def tool_list_opportunities(params: dict, token: str) -> dict:
    qp = {}
    for k in ("pipeline_id", "stage_id", "owner_id", "status", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("deals", token, params=qp)

def tool_get_opportunity(params: dict, token: str) -> dict:
    return piperun_get(f"deals/{params['deal_id']}", token)

def tool_list_companies(params: dict, token: str) -> dict:
    qp = {}
    for k in ("name", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("companies", token, params=qp)

def tool_get_company(params: dict, token: str) -> dict:
    return piperun_get(f"companies/{params['company_id']}", token)

def tool_list_persons(params: dict, token: str) -> dict:
    qp = {}
    for k in ("name", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("persons", token, params=qp)

def tool_get_person(params: dict, token: str) -> dict:
    return piperun_get(f"persons/{params['person_id']}", token)

def tool_list_pipelines(params: dict, token: str) -> dict:
    return piperun_get("pipelines", token)

def tool_get_pipeline(params: dict, token: str) -> dict:
    return piperun_get(f"pipelines/{params['pipeline_id']}", token)

def tool_list_stages(params: dict, token: str) -> dict:
    qp = {}
    if params.get("pipeline_id"):
        qp["pipeline_id"] = params["pipeline_id"]
    return piperun_get("stages", token, params=qp)

def tool_list_activities(params: dict, token: str) -> dict:
    qp = {}
    for k in ("deal_id", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("activities", token, params=qp)

def tool_list_proposals(params: dict, token: str) -> dict:
    qp = {}
    for k in ("deal_id", "page"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("proposals", token, params=qp)

def tool_get_proposal(params: dict, token: str) -> dict:
    return piperun_get(f"proposals/{params['proposal_id']}", token)

def tool_list_notes(params: dict, token: str) -> dict:
    qp = {}
    for k in ("deal_id", "page"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("notes", token, params=qp)

def tool_list_users(params: dict, token: str) -> dict:
    return piperun_get("users", token)

def tool_list_teams(params: dict, token: str) -> dict:
    return piperun_get("teams", token)

def tool_list_tags(params: dict, token: str) -> dict:
    return piperun_get("tags", token)

def tool_list_sources(params: dict, token: str) -> dict:
    return piperun_get("sources", token)

def tool_list_items(params: dict, token: str) -> dict:
    qp = {}
    if params.get("page"):
        qp["page"] = params["page"]
    return piperun_get("items", token, params=qp)

def tool_list_custom_fields(params: dict, token: str) -> dict:
    return piperun_get("customFields", token)


TOOLS = {
    "list_opportunities": tool_list_opportunities,
    "get_opportunity": tool_get_opportunity,
    "list_companies": tool_list_companies,
    "get_company": tool_get_company,
    "list_persons": tool_list_persons,
    "get_person": tool_get_person,
    "list_pipelines": tool_list_pipelines,
    "get_pipeline": tool_get_pipeline,
    "list_stages": tool_list_stages,
    "list_activities": tool_list_activities,
    "list_proposals": tool_list_proposals,
    "get_proposal": tool_get_proposal,
    "list_notes": tool_list_notes,
    "list_users": tool_list_users,
    "list_teams": tool_list_teams,
    "list_tags": tool_list_tags,
    "list_sources": tool_list_sources,
    "list_items": tool_list_items,
    "list_custom_fields": tool_list_custom_fields,
}

MCP_TOOLS_SCHEMA = [
    {"name": "list_opportunities", "description": "Listar oportunidades (deals) com filtros por funil, etapa, responsável e status.", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "integer"}, "stage_id": {"type": "integer"}, "owner_id": {"type": "integer"}, "status": {"type": "string", "enum": ["open", "won", "lost"]}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "get_opportunity", "description": "Detalhes de uma oportunidade pelo ID.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}}, "required": ["deal_id"]}},
    {"name": "list_companies", "description": "Listar empresas.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "get_company", "description": "Detalhes de uma empresa.", "inputSchema": {"type": "object", "properties": {"company_id": {"type": "integer"}}, "required": ["company_id"]}},
    {"name": "list_persons", "description": "Listar pessoas/contatos.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "get_person", "description": "Detalhes de uma pessoa.", "inputSchema": {"type": "object", "properties": {"person_id": {"type": "integer"}}, "required": ["person_id"]}},
    {"name": "list_pipelines", "description": "Listar funis de vendas.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_pipeline", "description": "Detalhes de um funil.", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "integer"}}, "required": ["pipeline_id"]}},
    {"name": "list_stages", "description": "Listar etapas de funil.", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "integer"}}}},
    {"name": "list_activities", "description": "Listar atividades.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "list_proposals", "description": "Listar propostas.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}, "page": {"type": "integer"}}}},
    {"name": "get_proposal", "description": "Detalhes de uma proposta.", "inputSchema": {"type": "object", "properties": {"proposal_id": {"type": "integer"}}, "required": ["proposal_id"]}},
    {"name": "list_notes", "description": "Listar notas.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}, "page": {"type": "integer"}}}},
    {"name": "list_users", "description": "Listar usuários.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_teams", "description": "Listar equipes.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_tags", "description": "Listar tags.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_sources", "description": "Listar origens de oportunidades.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_items", "description": "Listar itens (produtos/serviços).", "inputSchema": {"type": "object", "properties": {"page": {"type": "integer"}}}},
    {"name": "list_custom_fields", "description": "Listar campos customizados.", "inputSchema": {"type": "object", "properties": {}}},
]


# =============================================================================
# MCP PROTOCOL
# =============================================================================

def handle_mcp_request(body: dict, piperun_token: str) -> dict:
    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-piperun", "version": "2.0.0"}}}
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
            result = TOOLS[tool_name](tool_args, piperun_token)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}], "isError": False}}
        except requests.exceptions.HTTPError as e:
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro PipeRun: {e.response.text if e.response else str(e)}"}], "isError": True}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro: {str(e)}"}], "isError": True}}
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


# =============================================================================
# LOGIN PAGE HTML
# =============================================================================

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PipeRun - Autorizar MCP</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 420px; width: 90%; }
        h1 { color: #e53935; margin: 0 0 8px; font-size: 24px; }
        p { color: #666; margin: 0 0 24px; font-size: 14px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #333; }
        input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
        input:focus { outline: none; border-color: #e53935; }
        button { width: 100%; padding: 14px; background: #e53935; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 16px; }
        button:hover { background: #c62828; }
        .help { font-size: 12px; color: #999; margin-top: 12px; }
        .help a { color: #e53935; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🔗 PipeRun</h1>
        <p>Cole seu token da API para conectar ao QuickSight.</p>
        <form method="POST" action="{action_url}">
            <input type="hidden" name="state" value="{state}">
            <label for="token">Token da API PipeRun</label>
            <input type="password" id="token" name="token" placeholder="Cole seu token aqui" required>
            <button type="submit">Autorizar</button>
        </form>
        <p class="help">Encontre seu token em <a href="https://app.pipe.run/v2/me/user-data" target="_blank">Meus Dados</a> ou em Configurações &gt; Integrações &gt; API.</p>
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
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    headers = event.get("headers", {})
    auth_header = headers.get("authorization", "")
    accept_header = headers.get("accept", "")
    qs = event.get("queryStringParameters", {}) or {}

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
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        })

    # =========================================================================
    # TOKEN ENDPOINT
    # =========================================================================
    if path == "/token" and method == "POST":
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            import base64
            body_str = base64.b64decode(body_str).decode("utf-8")
        params = dict(urllib.parse.parse_qsl(body_str))
        code = params.get("code", "")
        if code and get_piperun_token(code):
            return resp_json(200, {"access_token": code, "token_type": "Bearer", "expires_in": 2592000})
        return resp_json(400, {"error": "invalid_grant"})

    # =========================================================================
    # REGISTER
    # =========================================================================
    if path == "/register" and method == "POST":
        return resp_json(201, {"client_id": "piperun-mcp", "client_name": "PipeRun MCP", "redirect_uris": [], "grant_types": ["authorization_code"], "response_types": ["code"], "token_endpoint_auth_method": "none"})

    # =========================================================================
    # /mcp and /authorize — LOGIN or MCP
    # =========================================================================
    if path in ("/mcp", "/authorize"):

        # With Bearer → MCP request
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
            piperun_token = get_piperun_token(session_token)

            if not piperun_token:
                return {"statusCode": 401, "headers": {"WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"', "Content-Type": "application/json"}, "body": json.dumps({"error": "unauthorized"})}

            if method == "POST":
                body_str = event.get("body", "{}")
                if event.get("isBase64Encoded"):
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8")
                body = json.loads(body_str)
                result = handle_mcp_request(body, piperun_token)
                if result is None:
                    return {"statusCode": 202, "headers": {"Content-Type": "application/json"}, "body": ""}
                if "text/event-stream" in accept_header:
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": f"event: message\ndata: {json.dumps(result, ensure_ascii=False, default=str)}\n\n"}
                return resp_json(200, result)

            if method == "GET":
                if "text/event-stream" in accept_header:
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": "event: open\ndata: {}\n\n"}
                return resp_json(200, {"jsonrpc": "2.0", "id": None, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-piperun", "version": "2.0.0"}}})

        # Without Bearer — OAuth authorize
        if method == "GET" and qs.get("response_type") == "code":
            state = qs.get("state", secrets.token_urlsafe(32))
            redirect_uri = qs.get("redirect_uri", "")
            store_state(state, redirect_uri)
            # Show login page
            html = LOGIN_PAGE.replace("{action_url}", f"{base_url}/login").replace("{state}", state)
            return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}

        # No Bearer, no OAuth params
        return {"statusCode": 401, "headers": {"WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"', "Content-Type": "application/json"}, "body": json.dumps({"error": "unauthorized"})}

    # =========================================================================
    # /login POST — receive token from form
    # =========================================================================
    if path == "/login" and method == "POST":
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            import base64
            body_str = base64.b64decode(body_str).decode("utf-8")
        form = dict(urllib.parse.parse_qsl(body_str))
        piperun_token = form.get("token", "")
        state = form.get("state", "")

        if not piperun_token:
            return {"statusCode": 400, "headers": {"Content-Type": "text/html"}, "body": "<h2>Token obrigatório</h2>"}

        # Validate token with PipeRun
        try:
            resp = requests.get(f"{PIPERUN_BASE_URL}/me", headers={"token": piperun_token, "Accept": "application/json"}, timeout=10)
            if not resp.ok:
                return {"statusCode": 400, "headers": {"Content-Type": "text/html"}, "body": "<h2>Token inválido. Verifique e tente novamente.</h2>"}
        except Exception:
            pass  # If validation fails, still allow (API might be down)

        # Generate session token and store mapping
        session_token = secrets.token_urlsafe(48)
        store_token(session_token, piperun_token)

        # Redirect back to QuickSight
        state_data = get_state(state)
        redirect_uri = state_data.get("redirect_uri", "") if state_data else ""

        if redirect_uri:
            sep = "&" if "?" in redirect_uri else "?"
            return {"statusCode": 302, "headers": {"Location": f"{redirect_uri}{sep}code={session_token}&state={state}"}, "body": ""}

        return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": f"<h2>✅ Autorizado!</h2><p>Token: <code>{session_token}</code></p>"}

    return resp_json(404, {"error": "Not found"})


def resp_json(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}
