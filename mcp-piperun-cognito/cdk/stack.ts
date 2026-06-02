import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigatewayv2Integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";

export class McpPiperunCognitoStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================================
    // COGNITO USER POOL
    // =========================================================================
    const userPool = new cognito.UserPool(this, "McpPiperunUserPool", {
      userPoolName: "mcp-piperun-users",
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
        fullname: { required: true, mutable: true },
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Cognito Domain (Hosted UI)
    const cognitoDomain = userPool.addDomain("McpPiperunDomain", {
      cognitoDomain: { domainPrefix: "mcp-piperun-dati" },
    });

    // Resource Server (custom scopes)
    const resourceServer = userPool.addResourceServer("PiperunResourceServer", {
      identifier: "piperun",
      userPoolResourceServerName: "PipeRun API",
      scopes: [
        { scopeName: "read", scopeDescription: "Leitura de dados do PipeRun" },
        { scopeName: "write", scopeDescription: "Escrita de dados no PipeRun" },
      ],
    });

    // App Client for Amazon Quick Suite (with secret - required by QuickSight)
    const appClient = userPool.addClient("QuickSuiteClient", {
      userPoolClientName: "amazon-quick-suite",
      generateSecret: true,
      authFlows: { userSrp: true },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
          cognito.OAuthScope.resourceServer(resourceServer, {
            scopeName: "read",
            scopeDescription: "Leitura",
          }),
          cognito.OAuthScope.resourceServer(resourceServer, {
            scopeName: "write",
            scopeDescription: "Escrita",
          }),
        ],
        callbackUrls: [
          "https://quicksight.aws.amazon.com/oauth/callback",
          "https://us-east-1.quicksight.aws.amazon.com/sn/oauthcallback",
          "http://localhost:3000/callback",
        ],
        logoutUrls: ["https://quicksight.aws.amazon.com"],
      },
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
    });

    // App Client for login page (no secret - used by browser JS for signup/login)
    const loginClient = userPool.addClient("LoginPageClient", {
      userPoolClientName: "mcp-piperun-login-page",
      generateSecret: false,
      authFlows: { userSrp: true, userPassword: true },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          "https://4hhm5xmcn4.execute-api.us-east-1.amazonaws.com/authorize",
        ],
        logoutUrls: ["https://4hhm5xmcn4.execute-api.us-east-1.amazonaws.com"],
      },
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
    });

    // =========================================================================
    // LAMBDA FUNCTION
    // =========================================================================
    const lambdaLayer = new lambda.LayerVersion(this, "McpPiperunLayer", {
      layerVersionName: "mcp-piperun-cognito-deps",
      code: lambda.Code.fromAsset("../lambda/layer"),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_13],
      description: "Dependencies: requests, aws-lambda-powertools, PyJWT",
    });

    const mcpFunction = new lambda.Function(this, "McpPiperunFunction", {
      functionName: "mcp-piperun-cognito",
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "handler.handler",
      code: lambda.Code.fromAsset("../lambda", {
        exclude: ["layer/**", "requirements.txt", "__pycache__"],
      }),
      layers: [lambdaLayer],
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      architecture: lambda.Architecture.X86_64,
      tracing: lambda.Tracing.ACTIVE,
      environment: {
        PIPERUN_BASE_URL: "https://api.pipe.run/v1",
        COGNITO_USER_POOL_ID: userPool.userPoolId,
        COGNITO_REGION: this.region,
        COGNITO_APP_CLIENT_ID: appClient.userPoolClientId,
        COGNITO_LOGIN_CLIENT_ID: loginClient.userPoolClientId,
        COGNITO_DOMAIN: "mcp-piperun-dati",
        SECRETS_PREFIX: "/dati/piperun/users",
        POWERTOOLS_SERVICE_NAME: "mcp-piperun-cognito",
        POWERTOOLS_METRICS_NAMESPACE: "MCPPipeRunCognito",
        LOG_LEVEL: "INFO",
      },
      logRetention: logs.RetentionDays.THREE_MONTHS,
    });

    // IAM: Secrets Manager access (scoped to user path)
    mcpFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "secretsmanager:GetSecretValue",
          "secretsmanager:CreateSecret",
          "secretsmanager:PutSecretValue",
        ],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:/dati/piperun/users/*`,
        ],
      })
    );

    // =========================================================================
    // API GATEWAY HTTP API
    // =========================================================================
    const httpApi = new apigatewayv2.HttpApi(this, "McpPiperunApi", {
      apiName: "mcp-piperun-cognito-api",
      description: "MCP PipeRun Server with Cognito OAuth",
      corsPreflight: {
        allowOrigins: ["*"],
        allowMethods: [
          apigatewayv2.CorsHttpMethod.GET,
          apigatewayv2.CorsHttpMethod.POST,
          apigatewayv2.CorsHttpMethod.OPTIONS,
        ],
        allowHeaders: [
          "Content-Type",
          "Authorization",
          "Accept",
        ],
        maxAge: cdk.Duration.hours(1),
      },
    });

    const lambdaIntegration = new apigatewayv2Integrations.HttpLambdaIntegration(
      "McpLambdaIntegration",
      mcpFunction
    );

    // Routes
    httpApi.addRoutes({
      path: "/.well-known/oauth-protected-resource",
      methods: [apigatewayv2.HttpMethod.GET],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/.well-known/oauth-authorization-server",
      methods: [apigatewayv2.HttpMethod.GET],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/mcp",
      methods: [apigatewayv2.HttpMethod.GET, apigatewayv2.HttpMethod.POST],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/register",
      methods: [apigatewayv2.HttpMethod.POST],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/register-token",
      methods: [apigatewayv2.HttpMethod.POST],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/authorize",
      methods: [apigatewayv2.HttpMethod.GET],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/token",
      methods: [apigatewayv2.HttpMethod.POST],
      integration: lambdaIntegration,
    });

    httpApi.addRoutes({
      path: "/signup",
      methods: [apigatewayv2.HttpMethod.GET],
      integration: lambdaIntegration,
    });

    // Update Lambda with API URL
    mcpFunction.addEnvironment("API_BASE_URL", httpApi.apiEndpoint);

    // =========================================================================
    // OUTPUTS
    // =========================================================================
    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: httpApi.apiEndpoint,
      description: "API Gateway HTTP API endpoint",
    });

    new cdk.CfnOutput(this, "McpEndpoint", {
      value: `${httpApi.apiEndpoint}/mcp`,
      description: "MCP Server endpoint (use this in Amazon Quick Suite)",
    });

    new cdk.CfnOutput(this, "CognitoUserPoolId", {
      value: userPool.userPoolId,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "CognitoAppClientId", {
      value: appClient.userPoolClientId,
      description: "Cognito App Client ID (with secret - for QuickSight)",
    });

    new cdk.CfnOutput(this, "CognitoLoginClientId", {
      value: loginClient.userPoolClientId,
      description: "Cognito Login Client ID (no secret - for browser login page)",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: `https://mcp-piperun-dati.auth.${this.region}.amazoncognito.com`,
      description: "Cognito Hosted UI domain",
    });

    new cdk.CfnOutput(this, "RegisterTokenEndpoint", {
      value: `${httpApi.apiEndpoint}/register-token`,
      description: "Endpoint para cadastro do token PipeRun",
    });

    new cdk.CfnOutput(this, "SignupPage", {
      value: `${httpApi.apiEndpoint}/signup`,
      description: "Pagina de auto-cadastro para usuarios",
    });
  }
}
