#!/usr/bin/env python3
import aws_cdk as cdk
from stack import CirclebackMcpStack

app = cdk.App()

CirclebackMcpStack(
    app,
    "circleback-mcp-server",
    env=cdk.Environment(account="601804669442", region="us-east-1"),
)

app.synth()
