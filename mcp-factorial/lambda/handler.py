"""
MCP Factorial - Lambda Handler com Function URL + Response Streaming
Suporta SSE (Server-Sent Events) para MCP Streamable HTTP transport.
OAuth 2.0 para autenticação com Factorial HR.
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

logger = Logger(service="mcp-factorial")
tracer = Tracer(service="mcp-factorial")
metrics = Metrics(service="mcp-factorial", namespace="MCPFactorial")

# Config
FACTORIAL_API_BASE = "https://api.factorialhr.com/api"
FACTORIAL_OAUTH_BASE = "https://api.factorialhr.com"
FACTORIAL_API_VERSION = "2026-01-01"

# Environment
SECRET_NAME = os.environ.get("FACTORIAL_SECRET_NAME", "mcp-factorial/oauth-credentials")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "mcp-factorial-tokens")
API_BASE_URL = os.environ.get("API_BASE_URL", "")

# AWS clients
dynamodb = boto3.resource("dynamodb")
secrets_client = boto3.client("secretsmanager")

_cached_credentials = None


def get_oauth_credentials() -> dict:
    """Recupera OAuth client_id e client_secret do Secrets Manager."""
    global _cached_credentials
    if _cached_credentials:
        return _cached_credentials
    response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    parsed = json.loads(response["SecretString"])
    if parsed.get("client_id") and parsed["client_id"] != "REPLACE_ME":
        _cached_credentials = parsed
        return _cached_credentials
    raise ValueError("Secret contains placeholder values")


def get_tokens_table():
    return dynamodb.Table(DYNAMODB_TABLE)


def store_token(access_token: str, token_data: dict):
    table = get_tokens_table()
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    table.put_item(Item={
        "token_hash": token_hash,
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": int(time.time()) + token_data.get("expires_in", 7200),
        "created_at": int(time.time()),
    })


def get_stored_token(access_token: str) -> dict | None:
    table = get_tokens_table()
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    response = table.get_item(Key={"token_hash": token_hash})
    return response.get("Item")


def store_auth_state(state: str, data: dict):
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


def get_valid_factorial_token(bearer_token: str) -> str | None:
    """Valida bearer token e retorna access_token do Factorial."""
    token_data = get_stored_token(bearer_token)
    if not token_data:
        return None
    if token_data.get("expires_at", 0) < time.time():
        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            creds = get_oauth_credentials()
            resp = requests.post(f"{FACTORIAL_OAUTH_BASE}/oauth/token", data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            }, timeout=30)
            if resp.ok:
                new_data = resp.json()
                store_token(bearer_token, new_data)
                return new_data["access_token"]
        return None
    return token_data.get("access_token")


# =============================================================================
# FACTORIAL API
# =============================================================================

def factorial_get(endpoint: str, access_token: str, params: dict = None) -> dict:
    url = f"{FACTORIAL_API_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# =============================================================================
# MCP TOOLS (READ-ONLY)
# =============================================================================

def tool_get_current_employee(params: dict, access_token: str) -> dict:
    data = factorial_get("/resources/api_public/credentials", access_token)
    if isinstance(data, dict) and "data" in data:
        employees = data["data"]
        if employees and isinstance(employees, list):
            return employees[0]
    return data


def tool_get_employee(params: dict, access_token: str) -> dict:
    full_name = params["full_name"]
    data = factorial_get("/resources/employees/employees", access_token,
                         params={"only_active": "true", "full_text_name": full_name})
    if isinstance(data, dict) and "data" in data:
        employees = data["data"]
        if employees and isinstance(employees, list):
            return employees[0]
    return data


def tool_get_available_vacation_days(params: dict, access_token: str) -> dict:
    employee_id = params["employee_id"]
    data = factorial_get("/resources/timeoff/allowance_stats", access_token,
                         params={"employee_ids[]": employee_id})
    if isinstance(data, dict) and "data" in data:
        stats = data["data"]
        if stats and isinstance(stats, list):
            return {"available_days": stats[0].get("available_days", 0), "details": stats[0]}
    return data


def tool_get_leave_types(params: dict, access_token: str) -> dict:
    data = factorial_get("/resources/timeoff/leave_types", access_token)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_read_time_offs(params: dict, access_token: str) -> dict:
    employee_id = params["employee_id"]
    query_params = {"employee_ids[]": employee_id, "include_deleted_leaves": "false"}
    if params.get("from_date"):
        query_params["from"] = params["from_date"]
    data = factorial_get("/resources/timeoff/leaves", access_token, params=query_params)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_list_shifts(params: dict, access_token: str) -> dict:
    """Lista apontamentos (shifts/clock-in/clock-out) de um funcionário."""
    employee_id = params["employee_id"]
    query_params = {"employee_ids[]": employee_id}
    if params.get("start_on"):
        query_params["start_on"] = params["start_on"]
    if params.get("end_on"):
        query_params["end_on"] = params["end_on"]
    data = factorial_get("/resources/attendance/shifts", access_token, params=query_params)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_list_company_holidays(params: dict, access_token: str) -> dict:
    """Lista feriados da empresa."""
    data = factorial_get("/resources/holidays/company_holidays", access_token)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_list_legal_entities(params: dict, access_token: str) -> dict:
    """Lista entidades legais da empresa."""
    data = factorial_get("/resources/companies/legal_entities", access_token)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_list_locations(params: dict, access_token: str) -> dict:
    """Lista localizações/escritórios da empresa."""
    data = factorial_get("/resources/locations/locations", access_token)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_list_employees(params: dict, access_token: str) -> dict:
    """Lista todos os funcionários ativos."""
    query_params = {"only_active": "true"}
    if params.get("team_id"):
        query_params["team_ids[]"] = params["team_id"]
    if params.get("legal_entity_id"):
        query_params["legal_entity_ids[]"] = params["legal_entity_id"]
    data = factorial_get("/resources/employees/employees", access_token, params=query_params)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def tool_list_teams(params: dict, access_token: str) -> dict:
    """Lista todas as equipes da empresa."""
    data = factorial_get("/resources/teams/teams", access_token)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


TOOLS = {
    "get_current_employee": tool_get_current_employee,
    "get_employee": tool_get_employee,
    "list_employees": tool_list_employees,
    "list_teams": tool_list_teams,
    "get_available_vacation_days": tool_get_available_vacation_days,
    "get_leave_types": tool_get_leave_types,
    "read_time_offs": tool_read_time_offs,
    "list_shifts": tool_list_shifts,
    "list_company_holidays": tool_list_company_holidays,
    "list_legal_entities": tool_list_legal_entities,
    "list_locations": tool_list_locations,
}

MCP_TOOLS_SCHEMA = [
    {"name": "get_current_employee", "description": "Retorna o nome completo e ID do funcionário logado.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_employee", "description": "Busca um funcionário pelo nome completo.", "inputSchema": {"type": "object", "properties": {"full_name": {"type": "string", "description": "Nome completo do funcionário"}}, "required": ["full_name"]}},
    {"name": "list_employees", "description": "Lista todos os funcionários ativos. Pode filtrar por equipe ou entidade legal.", "inputSchema": {"type": "object", "properties": {"team_id": {"type": "integer", "description": "Filtrar por ID da equipe"}, "legal_entity_id": {"type": "integer", "description": "Filtrar por ID da entidade legal"}}}},
    {"name": "list_teams", "description": "Lista todas as equipes da empresa com seus membros.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_available_vacation_days", "description": "Retorna os dias de férias disponíveis.", "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "integer", "description": "ID do funcionário"}}, "required": ["employee_id"]}},
    {"name": "get_leave_types", "description": "Lista tipos de folga disponíveis.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_time_offs", "description": "Lista folgas de um funcionário.", "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "integer", "description": "ID do funcionário"}, "from_date": {"type": "string", "description": "Data inicial YYYY-MM-DD"}}, "required": ["employee_id"]}},
    {"name": "list_shifts", "description": "Lista apontamentos de horas (shifts/clock-in/clock-out) de um funcionário.", "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "integer", "description": "ID do funcionário"}, "start_on": {"type": "string", "description": "Data inicial YYYY-MM-DD"}, "end_on": {"type": "string", "description": "Data final YYYY-MM-DD"}}, "required": ["employee_id"]}},
    {"name": "list_company_holidays", "description": "Lista feriados da empresa.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_legal_entities", "description": "Lista entidades legais (CNPJs/razões sociais) da empresa.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_locations", "description": "Lista localizações/escritórios da empresa.", "inputSchema": {"type": "object", "properties": {}}},
]


# =============================================================================
# MCP PROTOCOL
# =============================================================================

def handle_mcp_request(body: dict, access_token: str) -> dict:
    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "mcp-factorial", "version": "1.0.0"},
        }}
    elif method == "notifications/initialized":
        return None  # No response for notifications
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": MCP_TOOLS_SCHEMA}}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}
        factorial_token = get_valid_factorial_token(access_token)
        if not factorial_token:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": "Token expired"}}
        try:
            result = TOOLS[tool_name](tool_args, factorial_token)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}], "isError": False}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro: {str(e)}"}], "isError": True}}
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


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

    logger.info("Request", extra={"method": method, "path": path, "has_auth": bool(auth_header)})

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
            "authorization_endpoint": base_url + "/mcp",
            "token_endpoint": base_url + "/token",
            "registration_endpoint": base_url + "/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        })

    # =========================================================================
    # TOKEN ENDPOINT
    # =========================================================================
    if path == "/token" and method == "POST":
        return handle_token(event)

    # =========================================================================
    # REGISTER ENDPOINT
    # =========================================================================
    if path == "/register" and method == "POST":
        creds = get_oauth_credentials()
        body_str = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            import base64
            body_str = base64.b64decode(body_str).decode("utf-8")
        client_metadata = json.loads(body_str)
        return resp_json(201, {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "client_name": client_metadata.get("client_name", "MCP Client"),
            "redirect_uris": client_metadata.get("redirect_uris", []),
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })

    # =========================================================================
    # OAUTH CALLBACK
    # =========================================================================
    if path == "/oauth2-callback" and method == "GET":
        return handle_oauth_callback(event)

    # =========================================================================
    # /mcp ENDPOINT — handles both OAuth authorize and MCP requests
    # =========================================================================
    if path in ("/mcp", "/authorize"):

        # --- With Bearer token: MCP request ---
        if auth_header.startswith("Bearer "):
            bearer_token = auth_header[7:]

            if method == "POST":
                body_str = event.get("body", "{}")
                if event.get("isBase64Encoded"):
                    import base64
                    body_str = base64.b64decode(body_str).decode("utf-8")
                body = json.loads(body_str)
                result = handle_mcp_request(body, bearer_token)

                if result is None:
                    return {"statusCode": 202, "headers": {"Content-Type": "application/json"}, "body": ""}

                # Streamable HTTP: respond with SSE if accepted
                if "text/event-stream" in accept_header:
                    sse_body = f"event: message\ndata: {json.dumps(result, ensure_ascii=False, default=str)}\n\n"
                    return {
                        "statusCode": 200,
                        "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
                        "body": sse_body,
                    }
                return resp_json(200, result)

            if method == "GET":
                # SSE stream init or capabilities check
                if "text/event-stream" in accept_header:
                    # Return empty SSE to keep connection concept alive
                    return {
                        "statusCode": 200,
                        "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
                        "body": "event: open\ndata: {}\n\n",
                    }
                # JSON capabilities
                return resp_json(200, {
                    "jsonrpc": "2.0", "id": None,
                    "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-factorial", "version": "1.0.0"}},
                })

        # --- Without Bearer: OAuth authorize or 401 ---
        if method == "GET" and qs.get("response_type") == "code":
            # OAuth authorize request — redirect to Factorial
            return handle_authorize(event)

        # No Bearer, no OAuth params — return 401
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


def handle_authorize(event: dict) -> dict:
    qs = event.get("queryStringParameters", {}) or {}
    state = qs.get("state", secrets.token_urlsafe(32))
    redirect_uri = qs.get("redirect_uri", "")
    code_challenge = qs.get("code_challenge", "")
    code_challenge_method = qs.get("code_challenge_method", "S256")

    creds = get_oauth_credentials()
    base_url = API_BASE_URL or f"https://{event['requestContext']['domainName']}"

    store_auth_state(state, {"redirect_uri": redirect_uri, "code_challenge": code_challenge})

    params = {
        "client_id": creds["client_id"],
        "redirect_uri": "https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback",
        "response_type": "code",
        "state": state,
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = code_challenge_method

    url = f"{FACTORIAL_OAUTH_BASE}/oauth/authorize?{urllib.parse.urlencode(params)}"
    return {"statusCode": 302, "headers": {"Location": url}, "body": ""}


def handle_oauth_callback(event: dict) -> dict:
    qs = event.get("queryStringParameters", {}) or {}
    code = qs.get("code", "")
    state = qs.get("state", "")
    if not code:
        return resp_json(400, {"error": "Missing code"})

    state_data = get_auth_state(state)
    client_redirect_uri = state_data.get("redirect_uri", "") if state_data else ""

    creds = get_oauth_credentials()
    resp = requests.post(f"{FACTORIAL_OAUTH_BASE}/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "redirect_uri": "https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback",
    }, timeout=30)

    if not resp.ok:
        return resp_json(400, {"error": "token_exchange_failed", "details": resp.text})

    token_data = resp.json()
    mcp_token = secrets.token_urlsafe(48)
    store_token(mcp_token, token_data)

    if client_redirect_uri:
        sep = "&" if "?" in client_redirect_uri else "?"
        return {"statusCode": 302, "headers": {"Location": f"{client_redirect_uri}{sep}code={mcp_token}&state={state}"}, "body": ""}

    return resp_json(200, {"message": "Authorized", "token": mcp_token})


def handle_token(event: dict) -> dict:
    body_str = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64
        body_str = base64.b64decode(body_str).decode("utf-8")

    content_type = event.get("headers", {}).get("content-type", "")
    if "application/json" in content_type:
        params = json.loads(body_str)
    else:
        params = dict(urllib.parse.parse_qsl(body_str))

    grant_type = params.get("grant_type", "")
    code = params.get("code", "")
    code_verifier = params.get("code_verifier", "")

    logger.info("Token request", extra={"grant_type": grant_type, "has_code": bool(code)})

    creds = get_oauth_credentials()

    if grant_type == "authorization_code" and code:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "redirect_uri": "https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        resp = requests.post(f"{FACTORIAL_OAUTH_BASE}/oauth/token", data=data, timeout=30)
        logger.info("Factorial token response", extra={"status": resp.status_code})

        if resp.ok:
            token_data = resp.json()
            # Store and return our own token that maps to Factorial's
            mcp_token = secrets.token_urlsafe(48)
            store_token(mcp_token, token_data)
            return resp_json(200, {
                "access_token": mcp_token,
                "token_type": "Bearer",
                "expires_in": token_data.get("expires_in", 7200),
                "refresh_token": mcp_token,  # Use same token for refresh
            })
        else:
            logger.error("Token exchange failed", extra={"body": resp.text})
            return resp_json(400, {"error": "invalid_grant", "error_description": resp.text})

    elif grant_type == "refresh_token":
        refresh_token = params.get("refresh_token", "")
        token_data = get_stored_token(refresh_token)
        if token_data and token_data.get("refresh_token"):
            resp = requests.post(f"{FACTORIAL_OAUTH_BASE}/oauth/token", data={
                "grant_type": "refresh_token",
                "refresh_token": token_data["refresh_token"],
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            }, timeout=30)
            if resp.ok:
                new_data = resp.json()
                store_token(refresh_token, new_data)
                return resp_json(200, {
                    "access_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_in": new_data.get("expires_in", 7200),
                })
        return resp_json(400, {"error": "invalid_grant"})

    return resp_json(400, {"error": "unsupported_grant_type"})
