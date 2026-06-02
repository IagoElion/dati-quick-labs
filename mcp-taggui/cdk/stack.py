"""CDK Stack - MCP Taggui Server (Lambda Function URL + DynamoDB)."""

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
)
from constructs import Construct


class McpTagguiStack(Stack):
    """Stack para o MCP Server da TagguiRH com Function URL."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # DYNAMODB — armazena mapeamento token MCP -> token TagguiRH
        # =====================================================================

        tokens_table = dynamodb.Table(
            self,
            "TokensTable",
            table_name="mcp-taggui-tokens",
            partition_key=dynamodb.Attribute(
                name="token_hash",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expires_at",
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
            description="Dependencies for MCP Taggui Lambda",
        )

        # =====================================================================
        # LAMBDA FUNCTION with Function URL
        # =====================================================================

        lambda_function = _lambda.Function(
            self,
            "McpTagguiHandler",
            function_name="mcp-taggui-handler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.parent / "lambda")),
            layers=[powertools_layer, deps_layer],
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "DYNAMODB_TABLE": tokens_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "mcp-taggui",
                "POWERTOOLS_METRICS_NAMESPACE": "MCPTaggui",
                "LOG_LEVEL": "INFO",
                "API_BASE_URL": "",
            },
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            description="MCP Server para TagguiRH com Function URL",
        )

        # Permissões
        tokens_table.grant_read_write_data(lambda_function)

        # =====================================================================
        # FUNCTION URL
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

        Tags.of(self).add("Project", "mcp-taggui")
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
            description="MCP endpoint URL",
        )

        cdk.CfnOutput(
            self,
            "TokenEndpoint",
            value=fn_url.url + "token",
            description="Token endpoint — POST com taggui_token para obter token MCP",
        )
