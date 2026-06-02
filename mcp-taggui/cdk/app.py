#!/usr/bin/env python3
"""CDK App - MCP Taggui Server."""

import aws_cdk as cdk

from stack import McpTagguiStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or "us-east-1",
)

McpTagguiStack(
    app,
    "McpTagguiStack",
    env=env,
    description="MCP Server para TagguiRH via Lambda Function URL + DynamoDB",
)

app.synth()
