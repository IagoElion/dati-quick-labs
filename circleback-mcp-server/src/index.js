import express from 'express';
import { createServer } from 'http';
import serverless from 'serverless-http';
import { MCPServer } from './mcp-server.js';
import { CirclebackAuth, QS_CLIENT_ID, QS_CLIENT_SECRET } from './auth.js';

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const mcpServer = new MCPServer();
const auth = new CirclebackAuth();

// ========== Health Check ==========
app.get('/health', (req, res) => {
  res.json({ status: 'ok', version: '2.0.0', timestamp: new Date().toISOString() });
});

// ========== OAuth: Authorization Endpoint (QuickSight chama aqui) ==========
// QuickSight redireciona o usuário para cá com client_id, redirect_uri, state
app.get('/oauth/authorize', async (req, res) => {
  try {
    const { client_id, redirect_uri, state, response_type } = req.query;

    // Validar que é o QuickSight chamando
    if (client_id !== QS_CLIENT_ID) {
      return res.status(400).json({ error: 'client_id inválido' });
    }

    // Redirecionar para o Circleback
    const circlebackUrl = await auth.handleAuthorize(redirect_uri, state);
    res.redirect(circlebackUrl);
  } catch (error) {
    console.error('Authorize error:', error);
    res.status(500).json({ error: error.message });
  }
});

// ========== OAuth: Circleback Callback (Circleback redireciona aqui) ==========
// Após o usuário autorizar no Circleback, ele volta aqui
app.get('/oauth/circleback-callback', async (req, res) => {
  try {
    const { code, state, error: oauthError } = req.query;

    if (oauthError) {
      return res.status(400).json({
        error: 'Autorização negada pelo usuário no Circleback',
        detail: oauthError
      });
    }

    if (!code || !state) {
      return res.status(400).json({ error: 'Parâmetros code e state são obrigatórios' });
    }

    // Trocar code com Circleback e redirecionar para o QuickSight
    const qsRedirectUrl = await auth.handleCirclebackCallback(code, state);
    res.redirect(qsRedirectUrl);
  } catch (error) {
    console.error('Circleback callback error:', error);
    res.status(500).json({ error: error.message });
  }
});

// ========== OAuth: Token Endpoint (QuickSight chama aqui) ==========
// QuickSight troca o code por access_token via POST
app.post('/oauth/token', async (req, res) => {
  try {
    const { grant_type, code, refresh_token, client_id, client_secret } = req.body;

    // Validar credenciais do QuickSight
    if (!auth.validateQuickSightCredentials(client_id, client_secret)) {
      return res.status(401).json({ error: 'invalid_client', error_description: 'Credenciais inválidas' });
    }

    const tokenResponse = await auth.handleTokenExchange(grant_type, code, refresh_token);
    res.json(tokenResponse);
  } catch (error) {
    console.error('Token exchange error:', error);
    res.status(400).json({ error: 'invalid_grant', error_description: error.message });
  }
});

// ========== MCP Protocol Endpoint ==========
// QuickSight envia requests MCP aqui com o Bearer token do Circleback
app.post('/mcp', async (req, res) => {
  try {
    // O QuickSight manda o access_token no header Authorization
    const authHeader = req.headers['authorization'];
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Token de acesso obrigatório no header Authorization' });
    }

    const accessToken = authHeader.replace('Bearer ', '');
    const request = req.body;
    const response = await mcpServer.handleRequest(request, accessToken);
    res.json(response);
  } catch (error) {
    console.error('MCP Error:', error);
    res.status(500).json({ error: error.message });
  }
});

// ========== Lambda Handler ==========
export const handler = serverless(app);

// ========== Local Development Server ==========
if (process.env.NODE_ENV === 'development') {
  const PORT = process.env.PORT || 3000;
  createServer(app).listen(PORT, () => {
    console.log(`🚀 Circleback MCP Server rodando em http://localhost:${PORT}`);
    console.log(`📋 Health: http://localhost:${PORT}/health`);
  });
}
