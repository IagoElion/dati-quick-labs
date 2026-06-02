"""CDK Stack - MCP Factorial Server com OAuth 2.0 (Lambda Function URL + Streaming)."""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class McpFactorialStack(Stack):
    """Stack para o MCP Server do Factorial HR com OAuth 2.0 + Function URL."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # DYNAMODB
        # =====================================================================

        tokens_table = dynamodb.Table(
            self,
            "TokensTable",
            table_name="mcp-factorial-tokens",
            partition_key=dynamodb.Attribute(
                name="token_hash",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at",
        )

        # =====================================================================
        # SECRETS MANAGER (import existing)
        # =====================================================================

        secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "FactorialOAuthCredentials",
            "mcp-factorial/oauth-credentials",
        )

        # =====================================================================
        # LAMBDA LAYERS
        # =====================================================================

        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python313-x86_64:7",
        )

        deps_layer = _lambda.LayerVersion(
            self,
            "DepsLayer",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.parent / "layer")),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="Dependencies for MCP Factorial Lambda",
        )

        # =====================================================================
        # LAMBDA FUNCTION with Function URL (supports streaming)
        # =====================================================================

        lambda_function = _lambda.Function(
            self,
            "McpFactorialHandler",
            function_name="mcp-factorial-handler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.parent / "lambda")),
            layers=[powertools_layer, deps_layer],
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "FACTORIAL_SECRET_NAME": secret.secret_name,
                "DYNAMODB_TABLE": tokens_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "mcp-factorial",
                "POWERTOOLS_METRICS_NAMESPACE": "MCPFactorial",
                "LOG_LEVEL": "INFO",
                "API_BASE_URL": "",  # Will be set to Function URL after deploy
            },
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            description="MCP Server para Factorial HR com OAuth 2.0 + Function URL streaming",
        )

        # Permissões
        secret.grant_read(lambda_function)
        tokens_table.grant_read_write_data(lambda_function)

        # =====================================================================
        # FUNCTION URL (replaces API Gateway — supports response streaming)
        # =====================================================================

        fn_url = lambda_function.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE,
            invoke_mode=_lambda.InvokeMode.BUFFERED,
            cors=_lambda.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[_lambda.HttpMethod.ALL],
                allowed_headers=["*"],
                max_age=Duration.hours(1),
            ),
        )

        # =====================================================================
        # TAGS
        # =====================================================================

        Tags.of(self).add("Project", "mcp-factorial")
        Tags.of(self).add("Domain", "integrations")
        Tags.of(self).add("ManagedBy", "CDK")

        # =====================================================================
        # OUTPUTS
        # =====================================================================

        cdk.CfnOutput(
            self,
            "FunctionUrl",
            value=fn_url.url,
            description="Lambda Function URL (base)",
        )

        cdk.CfnOutput(
            self,
            "McpEndpoint",
            value=fn_url.url + "mcp",
            description="MCP endpoint URL para adicionar no QuickSight",
        )

        cdk.CfnOutput(
            self,
            "OAuthCallbackUrl",
            value=fn_url.url + "oauth2-callback",
            description="OAuth callback URL (para referência)",
        )
