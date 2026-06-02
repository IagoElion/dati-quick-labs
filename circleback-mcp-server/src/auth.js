import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import crypto from 'crypto';
import { TokenStore } from './token-store.js';

/**
 * O Lambda atua como OAuth Authorization Server para o QuickSight.
 * Usa PKCE (S256) para trocar tokens com o Circleback (public client).
 */

// Credenciais que o QuickSight vai usar para falar com o nosso Lambda
export const QS_CLIENT_ID = 'circleback-quicksight-mcp';
export const QS_CLIENT_SECRET = 'dati-qs-circleback-2024-secret';

export class CirclebackAuth {
  constructor() {
    this.tokenStore = new TokenStore();

    // Circleback OAuth endpoints
    this.circleback = {
      authorizationEndpoint: 'https://circleback.ai/api/oauth/authorize',
      tokenEndpoint: 'https://circleback.ai/api/oauth/access-token',
      registrationEndpoint: 'https://circleback.ai/api/oauth/register'
    };

    this.circlebackClientId = process.env.CIRCLEBACK_CLIENT_ID || null;
    this.baseUrl = process.env.API_BASE_URL || '';
  }

  // ========== PKCE Helpers ==========
  generateCodeVerifier() {
    return crypto.randomBytes(32).toString('base64url');
  }

  generateCodeChallenge(verifier) {
    return crypto.createHash('sha256').update(verifier).digest('base64url');
  }

  // ========== Client Registration ==========
  async ensureCirclebackClient() {
    if (this.circlebackClientId) return;

    const saved = await this.tokenStore.getTokens('__circleback_client__');
    if (saved && saved.accessToken) {
      this.circlebackClientId = saved.accessToken;
      return;
    }

    const response = await axios.post(this.circleback.registrationEndpoint, {
      client_name: 'Amazon QuickSight - Dati Quick Labs',
      redirect_uris: [`${this.baseUrl}/oauth/circleback-callback`],
      grant_types: ['authorization_code', 'refresh_token'],
      response_types: ['code'],
      token_endpoint_auth_method: 'none'
    });

    this.circlebackClientId = response.data.client_id;

    await this.tokenStore.saveTokens('__circleback_client__', {
      accessToken: this.circlebackClientId,
      refreshToken: 'none',
      expiresAt: Date.now() + 365 * 24 * 60 * 60 * 1000
    });
  }

  // ========== OAuth Flow ==========

  /**
   * PASSO 1: QuickSight chama /oauth/authorize
   * Gera PKCE code_verifier, salva, e redireciona para Circleback com code_challenge
   */
  async handleAuthorize(qsRedirectUri, qsState) {
    await this.ensureCirclebackClient();

    const internalState = uuidv4();
    const codeVerifier = this.generateCodeVerifier();
    const codeChallenge = this.generateCodeChallenge(codeVerifier);

    // Salvar state + code_verifier para usar no callback
    await this.tokenStore.saveOAuthState(internalState, JSON.stringify({
      qsRedirectUri,
      qsState,
      codeVerifier
    }));

    const params = new URLSearchParams({
      client_id: this.circlebackClientId,
      response_type: 'code',
      redirect_uri: `${this.baseUrl}/oauth/circleback-callback`,
      state: internalState,
      scope: 'user',
      code_challenge: codeChallenge,
      code_challenge_method: 'S256'
    });

    return `${this.circleback.authorizationEndpoint}?${params}`;
  }

  /**
   * PASSO 2: Circleback callback → troca code usando code_verifier (PKCE)
   */
  async handleCirclebackCallback(code, internalState) {
    const stateData = await this.tokenStore.getUserIdByState(internalState);
    if (!stateData) {
      throw new Error('State inválido ou expirado');
    }

    const { qsRedirectUri, qsState, codeVerifier } = JSON.parse(stateData);

    await this.ensureCirclebackClient();

    // Trocar code com code_verifier (PKCE)
    const tokenResponse = await axios.post(
      this.circleback.tokenEndpoint,
      new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        client_id: this.circlebackClientId,
        redirect_uri: `${this.baseUrl}/oauth/circleback-callback`,
        code_verifier: codeVerifier
      }).toString(),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );

    const { access_token, refresh_token, expires_in } = tokenResponse.data;

    // Gerar nosso code para o QuickSight
    const ourCode = uuidv4();

    await this.tokenStore.saveTokens(`code#${ourCode}`, {
      accessToken: access_token,
      refreshToken: refresh_token || '',
      expiresAt: Date.now() + (expires_in || 3600) * 1000
    });

    // Redirecionar para o QuickSight
    const redirectParams = new URLSearchParams({
      code: ourCode,
      state: qsState
    });

    return `${qsRedirectUri}?${redirectParams}`;
  }

  /**
   * PASSO 3: QuickSight chama POST /oauth/token
   */
  async handleTokenExchange(grantType, code, refreshToken) {
    if (grantType === 'authorization_code') {
      const tokenData = await this.tokenStore.getTokens(`code#${code}`);
      if (!tokenData) {
        throw new Error('Authorization code inválido ou expirado');
      }

      // Uso único
      await this.tokenStore.deleteTokens(`code#${code}`);

      return {
        access_token: tokenData.accessToken,
        refresh_token: tokenData.refreshToken,
        token_type: 'Bearer',
        expires_in: Math.max(1, Math.floor((tokenData.expiresAt - Date.now()) / 1000))
      };
    }

    if (grantType === 'refresh_token') {
      await this.ensureCirclebackClient();

      const response = await axios.post(
        this.circleback.tokenEndpoint,
        new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: this.circlebackClientId
        }).toString(),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );

      return {
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token || refreshToken,
        token_type: 'Bearer',
        expires_in: response.data.expires_in || 3600
      };
    }

    throw new Error(`grant_type não suportado: ${grantType}`);
  }

  validateQuickSightCredentials(clientId, clientSecret) {
    return clientId === QS_CLIENT_ID && clientSecret === QS_CLIENT_SECRET;
  }
}
