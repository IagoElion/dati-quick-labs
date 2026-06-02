"""Teste de tools/list via proxy MCP."""
import base64
import json
import urllib3

http = urllib3.PoolManager()

CLIENT_ID = "69dvq7gujmgmpk1cc2bvggciie"
CLIENT_SECRET = "6nir37ndmfmnie1731avrh4td51pu33b36118a7qa7k109ambrl"
TOKEN_URL = "https://partner-central-mcp.auth.us-east-1.amazoncognito.com/oauth2/token"
MCP_PROXY_URL = "https://7hk7vz4tb3.execute-api.us-east-1.amazonaws.com/prod/mcp"

# 1. Obter token (client_credentials para teste direto)
# Nota: vamos usar direto sem token, chamando o Lambda diretamente via boto3
import boto3

session = boto3.Session(profile_name="dati-quick-labs", region_name="us-east-1")
lambda_client = session.client("lambda")

# Testar initialize
print("=== 1. initialize ===")
init_payload = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "quicksight-test", "version": "1.0.0"},
    },
})

response = lambda_client.invoke(
    FunctionName="partner-central-mcp-proxy",
    Payload=json.dumps({"body": init_payload}),
)
result = json.loads(response["Payload"].read())
print(f"Status: {result.get('statusCode')}")
body = json.loads(result.get("body", "{}"))
print(f"Response: {json.dumps(body, indent=2)}")

# Testar notifications/initialized
print("\n=== 2. notifications/initialized ===")
notif_payload = json.dumps({
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
})

response = lambda_client.invoke(
    FunctionName="partner-central-mcp-proxy",
    Payload=json.dumps({"body": notif_payload}),
)
result = json.loads(response["Payload"].read())
print(f"Status: {result.get('statusCode')}")
print(f"Response: {result.get('body', '')}")

# Testar tools/list
print("\n=== 3. tools/list ===")
tools_payload = json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
})

response = lambda_client.invoke(
    FunctionName="partner-central-mcp-proxy",
    Payload=json.dumps({"body": tools_payload}),
)
result = json.loads(response["Payload"].read())
print(f"Status: {result.get('statusCode')}")
body = json.loads(result.get("body", "{}"))
print(f"Response: {json.dumps(body, indent=2)}")
