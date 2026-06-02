"""Teste service-to-service OAuth + MCP via Function URL."""
import json
import urllib3

http = urllib3.PoolManager()

FUNCTION_URL = "https://pd7izexylhghrlrqbel6a2nw5y0qihhc.lambda-url.us-east-1.on.aws"  # noqa
CLIENT_ID = "partner-central-mcp"
CLIENT_SECRET = "7fWZ-j7MjLexFsVDKQHJh5y1_AKHa7G-ExkuPQwY2qI"

# 1. Obter token via client_credentials
print("=== 1. Token (client_credentials) ===")
token_response = http.request(
    "POST",
    f"{FUNCTION_URL}/token",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    body=f"grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}",
)
print(f"Status: {token_response.status}")
token_data = json.loads(token_response.data.decode())
print(f"Response: {json.dumps(token_data, indent=2)}")

if token_response.status != 200:
    print("FALHOU no token!")
    exit(1)

access_token = token_data["access_token"]

# 2. Chamar MCP initialize
print("\n=== 2. MCP initialize ===")
mcp_response = http.request(
    "POST",
    f"{FUNCTION_URL}/mcp",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    },
    body=json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-service-auth", "version": "1.0.0"},
        },
    }).encode(),
)
print(f"Status: {mcp_response.status}")
print(f"Response: {mcp_response.data.decode()[:500]}")

# 3. Chamar tools/list
print("\n=== 3. MCP tools/list ===")
tools_response = http.request(
    "POST",
    f"{FUNCTION_URL}/mcp",
    headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    },
    body=json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }).encode(),
)
print(f"Status: {tools_response.status}")
resp = json.loads(tools_response.data.decode())
if "result" in resp and "tools" in resp["result"]:
    for tool in resp["result"]["tools"]:
        print(f"  - {tool['name']}: {tool['description'][:80]}...")
else:
    print(f"Response: {json.dumps(resp, indent=2)[:500]}")
