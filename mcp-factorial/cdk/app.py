#!/usr/bin/env python3
"""CDK App - MCP Factorial Server com OAuth 2.0."""

import aws_cdk as cdk

from stack import McpFactorialStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

McpFactorialStack(
    app,
    "McpFactorialStack",
    env=env,
    description="MCP Server para Factorial HR com OAuth 2.0 via API Gateway + Lambda + DynamoDB",
)

app.synth()
