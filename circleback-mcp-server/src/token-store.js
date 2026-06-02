import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, PutCommand, DeleteCommand } from '@aws-sdk/lib-dynamodb';

const TABLE_NAME = process.env.TOKEN_TABLE || 'circleback-mcp-tokens';

const client = new DynamoDBClient({ region: process.env.AWS_REGION || 'us-east-1' });
const docClient = DynamoDBDocumentClient.from(client);

export class TokenStore {
  /**
   * Salva tokens OAuth de um usuário no DynamoDB
   * @param {string} userId - Identificador único do usuário (email ou ID do Quick)
   * @param {object} tokenData - { accessToken, refreshToken, expiresAt }
   */
  async saveTokens(userId, tokenData) {
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        userId,
        accessToken: tokenData.accessToken,
        refreshToken: tokenData.refreshToken,
        expiresAt: tokenData.expiresAt,
        updatedAt: Date.now()
      }
    }));
  }

  /**
   * Recupera tokens de um usuário
   * @param {string} userId
   * @returns {object|null} tokenData ou null se não existir
   */
  async getTokens(userId) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { userId }
    }));

    return result.Item || null;
  }

  /**
   * Remove tokens de um usuário (logout/revoke)
   * @param {string} userId
   */
  async deleteTokens(userId) {
    await docClient.send(new DeleteCommand({
      TableName: TABLE_NAME,
      Key: { userId }
    }));
  }

  /**
   * Salva state temporário do OAuth flow para vincular ao userId
   * @param {string} state - OAuth state parameter
   * @param {string} userId - Quem iniciou o flow
   */
  async saveOAuthState(state, userId) {
    await docClient.send(new PutCommand({
      TableName: TABLE_NAME,
      Item: {
        userId: `oauth_state#${state}`,
        linkedUserId: userId,
        createdAt: Date.now(),
        // TTL de 10 minutos para limpar states expirados
        ttl: Math.floor(Date.now() / 1000) + 600
      }
    }));
  }

  /**
   * Recupera o userId vinculado a um OAuth state
   * @param {string} state
   * @returns {string|null} userId
   */
  async getUserIdByState(state) {
    const result = await docClient.send(new GetCommand({
      TableName: TABLE_NAME,
      Key: { userId: `oauth_state#${state}` }
    }));

    return result.Item?.linkedUserId || null;
  }
}
