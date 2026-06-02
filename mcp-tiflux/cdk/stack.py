"""CDK Stack - MCP Tiflux Server (Lambda + API Gateway HTTP API)."""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class McpTifluxStack(Stack):
    """Stack para o MCP Server do Tiflux Helpdesk."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # SECRETS MANAGER - Token do Tiflux (importa secret existente)
        # =====================================================================

        secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "TifluxApiToken",
            secret_name="mcp-tiflux/api-token",
        )

        # =====================================================================
        # LAMBDA LAYER - Powertools
        # =====================================================================

        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python313-x86_64:7",
        )

        # =====================================================================
        # LAMBDA LAYER - Dependencies (requests)
        # =====================================================================

        deps_layer = _lambda.LayerVersion(
            self,
            "DepsLayer",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.parent / "layer")),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="Dependencies for MCP Tiflux Lambda (requests)",
        )

        # =====================================================================
        # LAMBDA FUNCTION
        # =====================================================================

        lambda_function = _lambda.Function(
            self,
            "McpTifluxHandler",
            function_name="mcp-tiflux-handler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.parent / "lambda")),
            layers=[powertools_layer, deps_layer],
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "TIFLUX_BASE_URL": "https://api.tiflux.com/api/v2",
                "TIFLUX_SECRET_NAME": secret.secret_name,
                "POWERTOOLS_SERVICE_NAME": "mcp-tiflux",
                "POWERTOOLS_METRICS_NAMESPACE": "MCPTiflux",
                "LOG_LEVEL": "INFO",
            },
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            description="MCP Server para Tiflux Helpdesk - processa requests JSON-RPC 2.0",
        )

        # Permissão para ler o secret
        secret.grant_read(lambda_function)

        # =====================================================================
        # API GATEWAY HTTP API
        # =====================================================================

        http_api = apigwv2.HttpApi(
            self,
            "McpTifluxApi",
            api_name="mcp-tiflux-api",
            description="API Gateway HTTP para MCP Server do Tiflux Helpdesk com OAuth",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # Integração Lambda
        lambda_integration = integrations.HttpLambdaIntegration(
            "McpLambdaIntegration",
            handler=lambda_function,
        )

        # Rota POST /mcp (MCP endpoint principal)
        http_api.add_routes(
            path="/mcp",
            methods=[apigwv2.HttpMethod.POST, apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )

        # Rota POST / (fallback MCP)
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.POST, apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )

        # Rota /token (OAuth token endpoint)
        http_api.add_routes(
            path="/token",
            methods=[apigwv2.HttpMethod.POST, apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )

        # Rota /token/sse (SSE endpoint)
        http_api.add_routes(
            path="/token/sse",
            methods=[apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )

        # Rota /register (OAuth dynamic client registration)
        http_api.add_routes(
            path="/register",
            methods=[apigwv2.HttpMethod.POST],
            integration=lambda_integration,
        )

        # Rotas /.well-known (OAuth discovery)
        http_api.add_routes(
            path="/.well-known/oauth-protected-resource",
            methods=[apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )
        http_api.add_routes(
            path="/.well-known/oauth-authorization-server",
            methods=[apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )
        http_api.add_routes(
            path="/.well-known/openid-configuration",
            methods=[apigwv2.HttpMethod.GET],
            integration=lambda_integration,
        )

        # =====================================================================
        # TAGS
        # =====================================================================

        Tags.of(self).add("Project", "mcp-tiflux")
        Tags.of(self).add("Domain", "integrations")
        Tags.of(self).add("ManagedBy", "CDK")

        # =====================================================================
        # OUTPUTS
        # =====================================================================

        cdk.CfnOutput(
            self,
            "ApiEndpoint",
            value=http_api.api_endpoint,
            description="URL base do MCP Server",
        )

        cdk.CfnOutput(
            self,
            "McpEndpoint",
            value=f"{http_api.api_endpoint}/mcp",
            description="URL completa do endpoint MCP (JSON-RPC 2.0)",
        )

        cdk.CfnOutput(
            self,
            "TokenEndpoint",
            value=f"{http_api.api_endpoint}/token",
            description="Token URL para OAuth config no QuickSight",
        )

        cdk.CfnOutput(
            self,
            "SecretArn",
            value=secret.secret_name,
            description="Nome do secret com o token do Tiflux",
        )

        cdk.CfnOutput(
            self,
            "LambdaFunctionName",
            value=lambda_function.function_name,
            description="Nome da Lambda function",
        )
