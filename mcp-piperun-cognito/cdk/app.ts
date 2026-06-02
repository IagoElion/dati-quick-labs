#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { McpPiperunCognitoStack } from "./stack";

const app = new cdk.App();

new McpPiperunCognitoStack(app, "McpPiperunCognitoStack", {
  env: {
    account: "601804669442",
    region: "us-east-1",
  },
  description: "MCP PipeRun Server with Cognito OAuth + Secrets Manager",
});
