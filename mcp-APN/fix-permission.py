"""Aplicar resource policy completa ao Lambda via add_permission com workaround."""
import json
import boto3

session = boto3.Session(profile_name="dati-quick-labs", region_name="us-east-1")
lambda_client = session.client("lambda")

function_name = "partner-central-mcp-proxy"
function_arn = f"arn:aws:lambda:us-east-1:601804669442:function:{function_name}"

# A policy completa que precisamos (igual PipeRun/Factorial)
policy = json.dumps({
    "Version": "2012-10-17",
    "Id": "default",
    "Statement": [
        {
            "Sid": "AllowPublicInvokeFunctionUrl",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "lambda:InvokeFunctionUrl",
            "Resource": function_arn,
            "Condition": {
                "StringEquals": {
                    "lambda:FunctionUrlAuthType": "NONE"
                }
            }
        },
        {
            "Sid": "AllowPublicInvokeViaFunctionUrl",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "lambda:InvokeFunction",
            "Resource": function_arn,
            "Condition": {
                "Bool": {
                    "lambda:InvokedViaFunctionUrl": "true"
                }
            }
        }
    ]
})

# Tentar put_resource_policy (API mais recente)
try:
    response = lambda_client.put_resource_policy(
        ResourceArn=function_arn,
        Policy=policy,
    )
    print(f"Policy aplicada com sucesso! RevisionId: {response.get('RevisionId')}")
except Exception as e:
    print(f"put_resource_policy falhou: {e}")
    print("\nTentando abordagem alternativa...")
    
    # Alternativa: remover tudo e usar add_permission para a primeira,
    # depois tentar CloudFormation para a segunda
    
    # Verificar se existe a API
    try:
        # Listar métodos disponíveis
        methods = [m for m in dir(lambda_client) if 'policy' in m.lower() or 'permission' in m.lower()]
        print(f"Métodos disponíveis: {methods}")
    except:
        pass
