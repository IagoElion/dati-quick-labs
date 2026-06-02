from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigw,
    aws_logs as logs,
)
from constructs import Construct
import os


class CirclebackMcpStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ========== DynamoDB: Tokens por usuário ==========
        tokens_table = dynamodb.Table(
            self,
            "TokensTable",
            table_name="circleback-mcp-tokens",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            time_to_live_attribute="ttl",
        )

        # ========== Lambda Function ==========
        lambda_fn = _lambda.Function(
            self,
            "McpServerFn",
            function_name="circleback-mcp-server",
            runtime=_lambda.Runtime.NODEJS_18_X,
            handler="src/index.handler",
            code=_lambda.Code.from_asset(
                os.path.join(os.path.dirname(__file__), ".."),
                exclude=[
                    ".git",
                    ".git/**",
                    "infra",
                    "infra/**",
                    ".env*",
                    ".serverless",
                    ".serverless/**",
                    "node_modules/serverless/**",
                    "node_modules/serverless-offline/**",
                ],
            ),
            memory_size=256,
            timeout=Duration.seconds(30),
            environment={
                "TOKEN_TABLE": tokens_table.table_name,
                "NODE_ENV": "production",
            },
            log_retention=logs.RetentionDays.TWO_WEEKS,
        )

        # Permissões DynamoDB
        tokens_table.grant_read_write_data(lambda_fn)

        # ========== API Gateway ==========
        api = apigw.RestApi(
            self,
            "McpApi",
            rest_api_name="circleback-mcp-server",
            description="Circleback MCP Server - Proxy OAuth multi-tenant",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "x-user-id", "Authorization"],
            ),
        )

        # Root path
        api.root.add_method("ANY", apigw.LambdaIntegration(lambda_fn))

        # Proxy integration: todas as sub-rotas vão para o Lambda
        api.root.add_proxy(
            default_integration=apigw.LambdaIntegration(lambda_fn),
            any_method=True,
        )

        # Setar API_BASE_URL com a URL do API Gateway
        cfn_fn = lambda_fn.node.default_child
        cfn_fn.add_property_override(
            "Environment.Variables.API_BASE_URL",
            f"https://{api.rest_api_id}.execute-api.{self.region}.amazonaws.com/prod",
        )

        # ========== Outputs ==========
        CfnOutput(
            self,
            "ApiUrl",
            value=api.url,
            description="URL base do MCP Server",
        )

        CfnOutput(
            self,
            "McpEndpoint",
            value=f"{api.url}mcp",
            description="Endpoint MCP para o Quick",
        )

        CfnOutput(
            self,
            "OAuthLoginUrl",
            value=f"{api.url}oauth/authorize?userId=SEU_EMAIL",
            description="URL para cada usuário fazer login no Circleback",
        )

        CfnOutput(
            self,
            "TokensTableName",
            value=tokens_table.table_name,
            description="Tabela DynamoDB com tokens",
        )
