"""Teste de obtenção de token OAuth e chamada ao proxy MCP."""
import base64
import json
import urllib3

http = urllib3.PoolManager()

CLIENT_ID = "69dvq7gujmgmpk1cc2bvggciie"
CLIENT_SECRET = "6nir37ndmfmnie1731avrh4td51pu33b36118a7qa7k109ambrl"
TOKEN_URL = "https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/token"
MCP_PROXY_URL = "https://7hk7vz4tb3.execute-api.us-east-1.amazonaws.com/prod/mcp"

# 1. Obter token
print("=== Obtendo token OAuth ===")
creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
token_response = http.request(
    "POST",
    TOKEN_URL,
    headers={
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    body="grant_type=client_credentials&scope=mcp/invoke",
)
token_data = json.loads(token_response.data.decode())
print(f"Status: {token_response.status}")
print(f"Token type: {token_data.get('token_type')}")
print(f"Expires in: {token_data.get('expires_in')}s")

if token_response.status != 200:
    print(f"ERRO: {token_data}")
    exit(1)

access_token = token_data["access_token"]
print(f"Token obtido: {access_token[:20]}...")

# 2. Chamar proxy MCP
print("\n=== Chamando MCP Proxy (initialize) ===")
payload = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "dati-proxy-test", "version": "1.0.0"},
    },
})

mcp_response = http.request(
    "POST",
    MCP_PROXY_URL,
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    },
    body=payload.encode(),
)

print(f"Status: {mcp_response.status}")
print(f"Response: {mcp_response.data.decode()}")
