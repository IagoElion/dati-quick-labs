#!/usr/bin/env python3
"""CDK App - MCP PipeRun OAuth"""
import aws_cdk as cdk
from stack import McpPiperunStack

app = cdk.App()
McpPiperunStack(app, "mcp-piperun-oauth", env=cdk.Environment(
    account="601804669442",
    region="us-east-1",
))
app.synth()
