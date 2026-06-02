#!/usr/bin/env python3
"""CDK App - MCP Tiflux Server."""

import aws_cdk as cdk

from stack import McpTifluxStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

McpTifluxStack(
    app,
    "McpTifluxStack",
    env=env,
    description="MCP Server para integração com Tiflux Helpdesk via API Gateway + Lambda",
)

app.synth()
