"""
MCP Partner Central - Lambda Function URL
Proxy OAuth + MCP para Partner Central via SigV4.

Usa o mesmo padrão do mcp-piperun-oauth:
- QuickSight descobre OAuth via .well-known
- /mcp GET com response_type=code → auto-gera code (sem login)
- /token troca code por access_token
- /mcp POST com Bearer → proxy para Partner Central via SigV4
"""

import json
import os
import hmac
import hashlib
import time
import urllib.parse
import base64
from typing import Any

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import urllib3

http = urllib3.PoolManager()

# Partner Central Config
MCP_ENDPOINT = "https://partnercentral-agents-mcp.us-east-1.api.aws/mcp"
ROLE_ARN = "arn:aws:iam::107028717321:role/PartnerCentralMCPRole"
EXTERNAL_ID = "partner-central-mcp-proxy"
SERVICE_NAME = "partnercentral-agents-mcp"
REGION = "us-east-1"

# Environment
SECRET_NAME = os.environ.get("SECRET_NAME", "mcp-partner-central/oauth-credentials")
API_BASE_URL = os.environ.get("API_BASE_URL", "")

# AWS clients
sts_client = boto3.client("sts", region_name=REGION)
secrets_client = boto3.client("secretsmanager", region_name=REGION)

# Cache
_oauth_creds = None


def get_oauth_credentials() -> dict:
    """Carrega client_id e client_secret do Secrets Manager (cached)."""
    global _oauth_creds
    if _oauth_creds:
        return _oauth_creds
    response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    _oauth_creds = json.loads(response["SecretString"])
    return _oauth_creds


def generate_hmac_token(purpose: str) -> str:
    """Gera token HMAC stateless válido por 1 hora."""
    creds = get_oauth_credentials()
    hour_bucket = str(int(time.time()) // 3600)
    message = f"{purpose}:{creds['client_id']}:{hour_bucket}"
    return hmac.new(creds["client_secret"].encode(), message.encode(), hashlib.sha256).hexdigest()


def validate_hmac_token(token: str, purpose: str) -> bool:
    """Valida token HMAC (aceita hora atual e anterior)."""
    creds = get_oauth_credentials()
    current_bucket = int(time.time()) // 3600
    for bucket in [current_bucket, current_bucket - 1]:
        message = f"{purpose}:{creds['client_id']}:{bucket}"
        expected = hmac.new(creds["client_secret"].encode(), message.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(token, expected):
            return True
    return False


# =============================================================================
# SIGV4 PROXY TO PARTNER CENTRAL
# =============================================================================

def get_assumed_credentials():
    """Assume role na conta APN e retorna credenciais temporárias."""
    response = sts_client.assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName="mcp-proxy-session",
        ExternalId=EXTERNAL_ID,
        DurationSeconds=900,
    )
    creds = response["Credentials"]
    return Credentials(
        access_key=creds["AccessKeyId"],
        secret_key=creds["SecretAccessKey"],
        token=creds["SessionToken"],
    )


def forward_to_partner_central(payload: str, mcp_session_id: str = None) -> dict:
    """Assina com SigV4 e faz forward para o Partner Central MCP endpoint."""
    credentials = get_assumed_credentials()

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if mcp_session_id:
        headers["Mcp-Session-Id"] = mcp_session_id

    request = AWSRequest(method="POST", url=MCP_ENDPOINT, data=payload, headers=headers)
    SigV4Auth(credentials, SERVICE_NAME, REGION).add_auth(request)

    response = http.request(
        "POST",
        MCP_ENDPOINT,
        body=payload.encode("utf-8"),
        headers=dict(request.headers),
    )

    return {
        "status": response.status,
        "body": response.data.decode("utf-8"),
        "headers": dict(response.headers) if response.headers else {},
    }


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def handler(event: dict, context: Any) -> dict:
    """Lambda handler."""
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "/")
    headers = event.get("headers", {})
    auth_header = headers.get("authorization", "")
    accept_header = headers.get("accept", "")
    qs = event.get("queryStringParameters", {}) or {}

    base_url = API_BASE_URL or f"https://{event['requestContext']['domainName']}"

    print(f"[REQUEST] {method} {path}")

    # =========================================================================
    # WELL-KNOWN ENDPOINTS
    # =========================================================================
    if "/.well-known/" in path:
        if "oauth-protected-resource" in path:
            return resp_json(200, {
                "resource": base_url + "/mcp",
                "authorization_servers": [base_url],
                "bearer_methods_supported": ["header"],
            })
        if "oauth-authorization-server" in path:
            return resp_json(200, {
                "issuer": base_url,
                "authorization_endpoint": base_url + "/mcp",
                "token_endpoint": base_url + "/token",
                "registration_endpoint": base_url + "/register",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "client_credentials"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
            })
        if "openid-configuration" in path:
            return resp_json(200, {
                "issuer": base_url,
                "token_endpoint": base_url + "/token",
                "authorization_endpoint": base_url + "/mcp",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "client_credentials"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
            })
        return resp_json(404, {"error": "Not found"})

    # =========================================================================
    # REGISTER
    # =========================================================================
    if path == "/register" and method == "POST":
        creds = get_oauth_credentials()
        return resp_json(201, {
            "client_id": creds["client_id"],
            "client_name": "Partner Central MCP",
            "redirect_uris": [],
            "grant_types": ["authorization_code", "client_credentials"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        })

    # =========================================================================
    # TOKEN ENDPOINT
    # =========================================================================
    if path == "/token" and method == "POST":
        return handle_token(event)

    # =========================================================================
    # /login POST — recebe chave de acesso
    # =========================================================================
    if path == "/login" and method == "POST":
        return handle_login(event, base_url)

    # =========================================================================
    # /mcp ENDPOINT
    # =========================================================================
    if path == "/mcp":

        # --- With Bearer token: MCP request ---
        if auth_header.startswith("Bearer "):
            bearer_token = auth_header[7:]
            if not validate_hmac_token(bearer_token, "access"):
                return resp_json(401, {"error": "invalid_token"})

            if method == "POST":
                body_str = get_body(event)
                body = json.loads(body_str) if body_str else {}
                mcp_session_id = headers.get("mcp-session-id", "")

                print(f"[MCP] method={body.get('method')} id={body.get('id')}")

                # Notifications: retornar 202 sem forward
                if body.get("method", "").startswith("notifications/"):
                    return {"statusCode": 202, "headers": {"Content-Type": "application/json"}, "body": ""}

                # Forward to Partner Central
                result = forward_to_partner_central(json.dumps(body), mcp_session_id or None)

                response_headers = {"Content-Type": "application/json"}
                upstream_session = result["headers"].get("mcp-session-id") or result["headers"].get("Mcp-Session-Id")
                if upstream_session:
                    response_headers["Mcp-Session-Id"] = upstream_session

                if result["status"] == 200:
                    if "text/event-stream" in accept_header:
                        response_headers["Content-Type"] = "text/event-stream"
                        response_headers["Cache-Control"] = "no-cache"
                        return {"statusCode": 200, "headers": response_headers, "body": f"event: message\ndata: {result['body']}\n\n"}
                    return {"statusCode": 200, "headers": response_headers, "body": result["body"]}
                else:
                    print(f"[ERROR] upstream={result['status']}")
                    return {"statusCode": result["status"], "headers": response_headers, "body": result["body"]}

            if method == "GET":
                # OAuth authorize request
                if qs.get("response_type") == "code":
                    return handle_authorize(event, base_url)

                # SSE or capabilities
                if "text/event-stream" in accept_header:
                    return {"statusCode": 200, "headers": {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, "body": "event: open\ndata: {}\n\n"}
                return resp_json(200, {"jsonrpc": "2.0", "id": None, "result": {"protocolVersion": "2025-03-26", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-partner-central", "version": "1.0.0"}}})

            if method == "DELETE":
                return {"statusCode": 204, "headers": {}, "body": ""}

        # --- Without Bearer: OAuth authorize or 401 ---
        if method == "GET" and qs.get("response_type") == "code":
            return handle_authorize(event, base_url)

        # No Bearer, no OAuth params → 401
        return {
            "statusCode": 401,
            "headers": {
                "WWW-Authenticate": f'Bearer resource_metadata="{base_url}/.well-known/oauth-protected-resource"',
                "Content-Type": "application/json",
            },
            "body": json.dumps({"error": "unauthorized"}),
        }

    # Fallback
    return resp_json(404, {"error": "Not found", "path": path})


# =============================================================================
# HELPERS
# =============================================================================

def get_body(event: dict) -> str:
    body_str = event.get("body", "")
    if event.get("isBase64Encoded") and body_str:
        body_str = base64.b64decode(body_str).decode("utf-8")
    return body_str


def resp_json(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Partner Central MCP - Autorizar</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: white; border-radius: 12px; padding: 40px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 420px; width: 90%; }
        h1 { color: #232f3e; margin: 0 0 8px; font-size: 24px; }
        p { color: #666; margin: 0 0 24px; font-size: 14px; }
        label { display: block; font-weight: 600; margin-bottom: 8px; color: #333; }
        input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
        input:focus { outline: none; border-color: #ff9900; }
        button { width: 100%; padding: 14px; background: #ff9900; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 16px; }
        button:hover { background: #ec7211; }
        .error { color: #d13212; font-size: 13px; margin-top: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Partner Central MCP</h1>
        <p>Insira a chave de acesso para conectar ao Amazon Q.</p>
        <form method="POST" action="ACTION_URL">
            <input type="hidden" name="state" value="STATE_VAL">
            <input type="hidden" name="redirect_uri" value="REDIR_VAL">
            <label for="access_key">Chave de Acesso</label>
            <input type="password" id="access_key" name="access_key" placeholder="Cole a chave aqui" required>
            <button type="submit">Autorizar</button>
        </form>
        ERROR_MSG
    </div>
</body>
</html>"""


def handle_authorize(event: dict, base_url: str) -> dict:
    """OAuth authorize — mostra página pedindo chave de acesso."""
    qs = event.get("queryStringParameters", {}) or {}
    state = qs.get("state", "")
    redirect_uri = qs.get("redirect_uri", "")

    print(f"[AUTHORIZE] state={state} redirect_uri={redirect_uri}")

    html = LOGIN_PAGE.replace("ACTION_URL", base_url + "/login") \
                     .replace("STATE_VAL", state) \
                     .replace("REDIR_VAL", redirect_uri) \
                     .replace("ERROR_MSG", "")
    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}


def handle_login(event: dict, base_url: str) -> dict:
    """Recebe a chave de acesso, valida e redireciona com code."""
    body_str = get_body(event)
    form = dict(urllib.parse.parse_qsl(body_str))
    access_key = form.get("access_key", "")
    state = form.get("state", "")
    redirect_uri = form.get("redirect_uri", "")

    print(f"[LOGIN] has_key={bool(access_key)} state={state}")

    # Validar chave contra o client_secret do Secrets Manager
    creds = get_oauth_credentials()
    if access_key != creds["client_secret"]:
        html = LOGIN_PAGE.replace("ACTION_URL", base_url + "/login") \
                         .replace("STATE_VAL", state) \
                         .replace("REDIR_VAL", redirect_uri) \
                         .replace("ERROR_MSG", '<p class="error">Chave invalida. Tente novamente.</p>')
        return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}

    # Chave válida — gerar code e redirecionar
    code = generate_hmac_token("code")

    if redirect_uri:
        sep = "&" if "?" in redirect_uri else "?"
        location = f"{redirect_uri}{sep}code={code}&state={state}"
    else:
        location = f"https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback?code={code}&state={state}"

    return {"statusCode": 302, "headers": {"Location": location}, "body": ""}


def handle_token(event: dict) -> dict:
    """Token endpoint — aceita authorization_code e client_credentials."""
    body_str = get_body(event)
    headers = event.get("headers", {})
    content_type = headers.get("content-type", "")

    if "application/json" in content_type:
        params = json.loads(body_str) if body_str else {}
    else:
        params = dict(urllib.parse.parse_qsl(body_str))

    grant_type = params.get("grant_type", "")
    code = params.get("code", "")
    client_id = params.get("client_id", "")
    client_secret = params.get("client_secret", "")

    # Suportar Basic auth header
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        parts = decoded.split(":", 1)
        if len(parts) == 2:
            client_id = client_id or parts[0]
            client_secret = client_secret or parts[1]

    print(f"[TOKEN] grant_type={grant_type} client_id={client_id} has_code={bool(code)}")

    if grant_type == "authorization_code" and code:
        # Validar code HMAC
        if validate_hmac_token(code, "code"):
            access_token = generate_hmac_token("access")
            return resp_json(200, {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": access_token,
            })
        return resp_json(400, {"error": "invalid_grant", "error_description": "Invalid or expired code"})

    elif grant_type == "client_credentials":
        # Validar client credentials
        creds = get_oauth_credentials()
        if client_id and client_id != creds["client_id"]:
            return resp_json(401, {"error": "invalid_client"})
        if client_secret and client_secret != creds["client_secret"]:
            return resp_json(401, {"error": "invalid_client"})

        access_token = generate_hmac_token("access")
        return resp_json(200, {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        })

    elif grant_type == "refresh_token":
        access_token = generate_hmac_token("access")
        return resp_json(200, {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": access_token,
        })

    return resp_json(400, {"error": "unsupported_grant_type"})
