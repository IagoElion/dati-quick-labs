"""CDK Stack - MCP PipeRun White (Lambda + Function URL com OAuth)."""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    Stack,
    Tags,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class McpPiperunWhiteStack(Stack):
    """Stack para o MCP PipeRun White — leitura e escrita."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =====================================================================
        # SECRETS MANAGER - Token do PipeRun
        # =====================================================================

        secret = secretsmanager.Secret(
            self,
            "PipeRunApiToken",
            secret_name="mcp-piperun-white/api-token",
            description="Token da API do PipeRun CRM",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"token": "PLACEHOLDER"}',
                generate_string_key="placeholder",
            ),
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
            description="Dependencies for MCP PipeRun White (requests)",
        )

        # =====================================================================
        # LAMBDA FUNCTION
        # =====================================================================

        lambda_function = _lambda.Function(
            self,
            "McpPiperunWhiteHandler",
            function_name="mcp-piperun-white-handler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.parent / "lambda")),
            layers=[powertools_layer, deps_layer],
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "PIPERUN_BASE_URL": "https://api.pipe.run/v1",
                "PIPERUN_SECRET_NAME": "mcp-piperun-white/api-token",
                "POWERTOOLS_SERVICE_NAME": "mcp-piperun-white",
                "POWERTOOLS_METRICS_NAMESPACE": "MCPPipeRunWhite",
                "LOG_LEVEL": "INFO",
            },
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            description="MCP PipeRun White - Leitura e Escrita com OAuth",
        )

        secret.grant_read(lambda_function)

        # =====================================================================
        # LAMBDA FUNCTION URL
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

        Tags.of(self).add("Project", "mcp-piperun-white")
        Tags.of(self).add("Domain", "integrations")
        Tags.of(self).add("ManagedBy", "CDK")

        # =====================================================================
        # OUTPUTS
        # =====================================================================

        cdk.CfnOutput(self, "FunctionUrl", value=fn_url.url, description="Lambda Function URL (base)")
        cdk.CfnOutput(self, "McpEndpoint", value=fn_url.url + "mcp", description="MCP endpoint para QuickSight")
        cdk.CfnOutput(self, "TokenEndpoint", value=fn_url.url + "token", description="Token URL para OAuth")
        cdk.CfnOutput(self, "SecretArn", value=secret.secret_arn, description="ARN do secret para atualizar o token")
