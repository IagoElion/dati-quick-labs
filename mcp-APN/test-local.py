import sys
sys.path.insert(0, "lambda")
from lambda_function import handle_authorize

r = handle_authorize(
    {"queryStringParameters": {"state": "test123", "redirect_uri": "https://example.com/cb"}},
    "https://myserver.com"
)
print(f"Status: {r['statusCode']}")
print(r["body"][:300])
