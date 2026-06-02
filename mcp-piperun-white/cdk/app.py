#!/usr/bin/env python3
"""CDK App - MCP PipeRun White."""

import aws_cdk as cdk

from stack import McpPiperunWhiteStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

McpPiperunWhiteStack(
    app,
    "McpPiperunWhiteStack",
    env=env,
    description="MCP Server PipeRun White - Leitura e Escrita com OAuth para QuickSight",
)

app.synth()
