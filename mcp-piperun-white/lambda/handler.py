"""
MCP PipeRun White - Lambda Handler (READ + WRITE) com OAuth service-to-service
Proxy para a API do PipeRun CRM com autenticação OAuth client_credentials.
Versão white-label com operações de leitura E escrita.
"""

import json
import os
import secrets
import urllib.parse
import base64
from typing import Any

import boto3
import requests
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="mcp-piperun-white")
tracer = Tracer(service="mcp-piperun-white")
metrics = Metrics(service="mcp-piperun-white", namespace="MCPPipeRunWhite")

PIPERUN_BASE_URL = os.environ.get("PIPERUN_BASE_URL", "https://api.pipe.run/v1")
PIPERUN_SECRET_NAME = os.environ.get("PIPERUN_SECRET_NAME", "mcp-piperun-white/api-token")
API_BASE_URL = os.environ.get("API_BASE_URL", "")

_secrets_client = boto3.client("secretsmanager")
_cached_token = None


def get_piperun_token() -> str:
    """Recupera o token do PipeRun do Secrets Manager."""
    global _cached_token
    if _cached_token:
        return _cached_token
    response = _secrets_client.get_secret_value(SecretId=PIPERUN_SECRET_NAME)
    secret_data = json.loads(response["SecretString"])
    _cached_token = secret_data["token"]
    return _cached_token


def piperun_headers() -> dict:
    """Headers padrão para requests ao PipeRun."""
    return {
        "token": get_piperun_token(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@tracer.capture_method
def piperun_get(endpoint: str, params: dict = None) -> dict:
    """GET request para a API do PipeRun."""
    url = f"{PIPERUN_BASE_URL}/{endpoint}"
    logger.info("PipeRun GET", extra={"url": url, "params": params})
    response = requests.get(url, headers=piperun_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@tracer.capture_method
def piperun_post(endpoint: str, data: dict = None) -> dict:
    """POST request para a API do PipeRun."""
    url = f"{PIPERUN_BASE_URL}/{endpoint}"
    logger.info("PipeRun POST", extra={"url": url, "data": data})
    response = requests.post(url, headers=piperun_headers(), json=data, timeout=30)
    response.raise_for_status()
    return response.json()


@tracer.capture_method
def piperun_put(endpoint: str, data: dict = None) -> dict:
    """PUT request para a API do PipeRun."""
    url = f"{PIPERUN_BASE_URL}/{endpoint}"
    logger.info("PipeRun PUT", extra={"url": url, "data": data})
    response = requests.put(url, headers=piperun_headers(), json=data, timeout=30)
    response.raise_for_status()
    return response.json()


# =============================================================================
# TOOLS — LEITURA (GET/LIST)
# =============================================================================


def tool_list_opportunities(params: dict) -> dict:
    """Listar oportunidades com filtros opcionais."""
    qp = {}
    for k in ("pipeline_id", "stage_id", "owner_id", "status", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("deals", params=qp)


def tool_get_opportunity(params: dict) -> dict:
    """Ver detalhes de uma oportunidade específica."""
    return piperun_get(f"deals/{params['deal_id']}")


def tool_list_companies(params: dict) -> dict:
    """Listar empresas com filtros opcionais."""
    qp = {}
    for k in ("name", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("companies", params=qp)


def tool_get_company(params: dict) -> dict:
    """Ver detalhes de uma empresa."""
    return piperun_get(f"companies/{params['company_id']}")


def tool_list_persons(params: dict) -> dict:
    """Listar pessoas (contatos)."""
    qp = {}
    for k in ("name", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("persons", params=qp)


def tool_get_person(params: dict) -> dict:
    """Ver detalhes de uma pessoa."""
    return piperun_get(f"persons/{params['person_id']}")


def tool_list_pipelines(params: dict) -> dict:
    """Listar funis disponíveis."""
    return piperun_get("pipelines")


def tool_get_pipeline(params: dict) -> dict:
    """Ver detalhes de um funil."""
    return piperun_get(f"pipelines/{params['pipeline_id']}")


def tool_list_stages(params: dict) -> dict:
    """Listar etapas de funil."""
    qp = {}
    if params.get("pipeline_id"):
        qp["pipeline_id"] = params["pipeline_id"]
    return piperun_get("stages", params=qp)


def tool_list_activities(params: dict) -> dict:
    """Listar atividades."""
    qp = {}
    for k in ("deal_id", "page", "show"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("activities", params=qp)


def tool_list_proposals(params: dict) -> dict:
    """Listar propostas."""
    qp = {}
    for k in ("deal_id", "page"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("proposals", params=qp)


def tool_get_proposal(params: dict) -> dict:
    """Ver detalhes de uma proposta."""
    return piperun_get(f"proposals/{params['proposal_id']}")


def tool_list_notes(params: dict) -> dict:
    """Listar notas."""
    qp = {}
    for k in ("deal_id", "page"):
        if params.get(k):
            qp[k] = params[k]
    return piperun_get("notes", params=qp)


def tool_list_users(params: dict) -> dict:
    """Listar usuários."""
    return piperun_get("users")


def tool_list_teams(params: dict) -> dict:
    """Listar equipes."""
    return piperun_get("teams")


def tool_list_tags(params: dict) -> dict:
    """Listar tags."""
    return piperun_get("tags")


def tool_list_sources(params: dict) -> dict:
    """Listar origens de oportunidades."""
    return piperun_get("sources")


def tool_list_items(params: dict) -> dict:
    """Listar itens (produtos, serviços, MRR)."""
    qp = {}
    if params.get("page"):
        qp["page"] = params["page"]
    return piperun_get("items", params=qp)


def tool_list_custom_fields(params: dict) -> dict:
    """Listar campos customizados."""
    return piperun_get("customFields")


# =============================================================================
# TOOLS — ESCRITA (POST/PUT)
# =============================================================================


def tool_create_opportunity(params: dict) -> dict:
    """Criar uma nova oportunidade."""
    data = {}
    for k in ("title", "pipeline_id", "stage_id", "owner_id", "company_id", "person_id", "value", "source_id"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_post("deals", data=data)


def tool_update_opportunity(params: dict) -> dict:
    """Atualizar uma oportunidade existente."""
    deal_id = params.pop("deal_id")
    data = {}
    for k in ("title", "stage_id", "owner_id", "value", "status"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_put(f"deals/{deal_id}", data=data)


def tool_create_company(params: dict) -> dict:
    """Criar uma nova empresa."""
    data = {}
    for k in ("name", "cnpj", "email", "phone", "website", "address", "city", "state"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_post("companies", data=data)


def tool_update_company(params: dict) -> dict:
    """Atualizar dados de uma empresa."""
    company_id = params.pop("company_id")
    data = {}
    for k in ("name", "email", "phone", "website", "address", "city", "state"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_put(f"companies/{company_id}", data=data)


def tool_create_person(params: dict) -> dict:
    """Criar uma nova pessoa/contato."""
    data = {}
    for k in ("name", "email", "phone", "company_id", "cpf"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_post("persons", data=data)


def tool_update_person(params: dict) -> dict:
    """Atualizar dados de uma pessoa."""
    person_id = params.pop("person_id")
    data = {}
    for k in ("name", "email", "phone"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_put(f"persons/{person_id}", data=data)


def tool_create_activity(params: dict) -> dict:
    """Criar uma nova atividade vinculada a uma oportunidade."""
    data = {}
    for k in ("deal_id", "type", "subject", "description", "due_date", "owner_id"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_post("activities", data=data)


def tool_create_note(params: dict) -> dict:
    """Criar uma nota em uma oportunidade."""
    data = {}
    for k in ("deal_id", "content"):
        if params.get(k) is not None:
            data[k] = params[k]
    return piperun_post("notes", data=data)


# =============================================================================
# ROUTER
# =============================================================================

TOOLS = {
    # Leitura
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
    # Escrita
    "create_opportunity": tool_create_opportunity,
    "update_opportunity": tool_update_opportunity,
    "create_company": tool_create_company,
    "update_company": tool_update_company,
    "create_person": tool_create_person,
    "update_person": tool_update_person,
    "create_activity": tool_create_activity,
    "create_note": tool_create_note,
}


# =============================================================================
# MCP TOOLS SCHEMA
# =============================================================================

MCP_TOOLS_SCHEMA = [
    # --- Leitura ---
    {"name": "list_opportunities", "description": "Listar oportunidades (deals) do PipeRun com filtros opcionais por funil, etapa, responsável e status.", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "integer", "description": "ID do funil"}, "stage_id": {"type": "integer", "description": "ID da etapa"}, "owner_id": {"type": "integer", "description": "ID do responsável"}, "status": {"type": "string", "enum": ["open", "won", "lost"], "description": "Status"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "get_opportunity", "description": "Ver detalhes de uma oportunidade pelo ID.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer", "description": "ID da oportunidade"}}, "required": ["deal_id"]}},
    {"name": "list_companies", "description": "Listar empresas cadastradas.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "get_company", "description": "Ver detalhes de uma empresa.", "inputSchema": {"type": "object", "properties": {"company_id": {"type": "integer"}}, "required": ["company_id"]}},
    {"name": "list_persons", "description": "Listar pessoas/contatos.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "get_person", "description": "Ver detalhes de uma pessoa.", "inputSchema": {"type": "object", "properties": {"person_id": {"type": "integer"}}, "required": ["person_id"]}},
    {"name": "list_pipelines", "description": "Listar funis de vendas.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_pipeline", "description": "Ver detalhes de um funil.", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "integer"}}, "required": ["pipeline_id"]}},
    {"name": "list_stages", "description": "Listar etapas de funil.", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "integer"}}}},
    {"name": "list_activities", "description": "Listar atividades.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}, "page": {"type": "integer"}, "show": {"type": "integer"}}}},
    {"name": "list_proposals", "description": "Listar propostas.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}, "page": {"type": "integer"}}}},
    {"name": "get_proposal", "description": "Ver detalhes de uma proposta.", "inputSchema": {"type": "object", "properties": {"proposal_id": {"type": "integer"}}, "required": ["proposal_id"]}},
    {"name": "list_notes", "description": "Listar notas.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer"}, "page": {"type": "integer"}}}},
    {"name": "list_users", "description": "Listar usuários.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_teams", "description": "Listar equipes.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_tags", "description": "Listar tags.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_sources", "description": "Listar origens.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_items", "description": "Listar itens (produtos/serviços).", "inputSchema": {"type": "object", "properties": {"page": {"type": "integer"}}}},
    {"name": "list_custom_fields", "description": "Listar campos customizados.", "inputSchema": {"type": "object", "properties": {}}},
    # --- Escrita ---
    {"name": "create_opportunity", "description": "Criar uma nova oportunidade no PipeRun.", "inputSchema": {"type": "object", "properties": {"title": {"type": "string", "description": "Título da oportunidade"}, "pipeline_id": {"type": "integer", "description": "ID do funil"}, "stage_id": {"type": "integer", "description": "ID da etapa inicial"}, "owner_id": {"type": "integer", "description": "ID do responsável"}, "company_id": {"type": "integer", "description": "ID da empresa"}, "person_id": {"type": "integer", "description": "ID do contato"}, "value": {"type": "number", "description": "Valor da oportunidade"}, "source_id": {"type": "integer", "description": "ID da origem"}}, "required": ["title", "pipeline_id", "stage_id"]}},
    {"name": "update_opportunity", "description": "Atualizar uma oportunidade (mover etapa, alterar valor, status, responsável).", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer", "description": "ID da oportunidade"}, "title": {"type": "string"}, "stage_id": {"type": "integer", "description": "Nova etapa (mover no funil)"}, "owner_id": {"type": "integer"}, "value": {"type": "number"}, "status": {"type": "string", "enum": ["open", "won", "lost"]}}, "required": ["deal_id"]}},
    {"name": "create_company", "description": "Criar uma nova empresa.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string", "description": "Nome da empresa"}, "cnpj": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "website": {"type": "string"}, "address": {"type": "string"}, "city": {"type": "string"}, "state": {"type": "string", "description": "UF"}}, "required": ["name"]}},
    {"name": "update_company", "description": "Atualizar dados de uma empresa.", "inputSchema": {"type": "object", "properties": {"company_id": {"type": "integer"}, "name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "website": {"type": "string"}, "address": {"type": "string"}, "city": {"type": "string"}, "state": {"type": "string"}}, "required": ["company_id"]}},
    {"name": "create_person", "description": "Criar uma nova pessoa/contato.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string", "description": "Nome"}, "email": {"type": "string"}, "phone": {"type": "string"}, "company_id": {"type": "integer", "description": "Empresa associada"}, "cpf": {"type": "string"}}, "required": ["name"]}},
    {"name": "update_person", "description": "Atualizar dados de uma pessoa.", "inputSchema": {"type": "object", "properties": {"person_id": {"type": "integer"}, "name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}}, "required": ["person_id"]}},
    {"name": "create_activity", "description": "Criar atividade vinculada a uma oportunidade.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer", "description": "ID da oportunidade"}, "type": {"type": "string", "enum": ["call", "meeting", "task", "email", "lunch", "deadline"], "description": "Tipo"}, "subject": {"type": "string", "description": "Assunto"}, "description": {"type": "string"}, "due_date": {"type": "string", "description": "Data (YYYY-MM-DD)"}, "owner_id": {"type": "integer"}}, "required": ["deal_id", "type", "subject"]}},
    {"name": "create_note", "description": "Criar nota em uma oportunidade.", "inputSchema": {"type": "object", "properties": {"deal_id": {"type": "integer", "description": "ID da oportunidade"}, "content": {"type": "string", "description": "Conteúdo da nota"}}, "required": ["deal_id", "content"]}},
]


# =============================================================================
# MCP PROTOCOL (JSON-RPC 2.0)
# =============================================================================


def handle_mcp_request(body: dict) -> dict:
    """Processa uma requisição MCP (JSON-RPC 2.0)."""
    method = body.get("method", "")
    request_id = body.get("id")
    params = body.get("params", {})

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mcp-piperun-white", "version": "1.0.0"},
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
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}

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
            logger.error("PipeRun API error", extra={"tool": tool_name, "error": error_body})
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro PipeRun: {error_body}"}], "isError": True}}
        except Exception as e:
            logger.exception("Tool execution error", extra={"tool": tool_name})
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": f"Erro interno: {str(e)}"}], "isError": True}}

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
            "grant_types_supported": ["client_credentials"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        })

    # Discovery extras que o QuickSight tenta
    if path in ("/.well-known/openid-configuration", "/token/.well-known/openid-configuration", "/.well-known/oauth-protected-resource/token"):
        return resp_json(200, {
            "issuer": base_url,
            "token_endpoint": base_url + "/token",
            "authorization_endpoint": base_url + "/mcp",
            "grant_types_supported": ["client_credentials"],
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        })

    # =========================================================================
    # TOKEN ENDPOINT (client_credentials)
    # =========================================================================
    if path == "/token" and method == "POST" and not auth_header.startswith("Bearer "):
        body_str = event.get("body", "")
        if event.get("isBase64Encoded"):
            body_str = base64.b64decode(body_str).decode("utf-8")

        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            params = json.loads(body_str) if body_str else {}
        else:
            params = dict(urllib.parse.parse_qsl(body_str)) if body_str else {}

        client_id = params.get("client_id", "")
        client_secret = params.get("client_secret", "")

        # Suportar Basic Auth
        if not client_id and auth_header.startswith("Basic "):
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            if ":" in decoded:
                client_id, client_secret = decoded.split(":", 1)

        logger.info("Token request", extra={"client_id": client_id})

        # Aceitar qualquer request — gerar access_token
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
            "client_id": "mcp-piperun-white",
            "client_secret": "dati-mcp-piperun-white-2026",
            "client_name": "MCP PipeRun White",
            "grant_types": ["client_credentials"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        })

    # =========================================================================
    # MCP ENDPOINT — /mcp, /, /token, /token/sse
    # =========================================================================
    if path in ("/mcp", "/", "/token", "/token/sse"):

        # With Bearer → MCP request
        if auth_header.startswith("Bearer "):
            if method == "POST":
                body_str = event.get("body", "{}")
                if event.get("isBase64Encoded"):
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
                return resp_json(200, {"jsonrpc": "2.0", "id": None, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-piperun-white", "version": "1.0.0"}}})

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


def resp_json(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}
