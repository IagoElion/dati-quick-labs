import { tools } from './tools.js';
import { CirclebackClient } from './circleback-client.js';

export class MCPServer {
  constructor() {
    this.client = new CirclebackClient();
    this.tools = tools;
  }

  async handleRequest(request, accessToken) {
    const { jsonrpc, method, params, id } = request;

    try {
      let result;

      switch (method) {
        case 'initialize':
          result = this.handleInitialize();
          break;

        case 'tools/list':
          result = this.handleListTools();
          break;

        case 'tools/call':
          result = await this.handleToolCall(params, accessToken);
          break;

        default:
          throw new Error(`Método desconhecido: ${method}`);
      }

      return {
        jsonrpc,
        result,
        id
      };
    } catch (error) {
      return {
        jsonrpc,
        error: {
          code: -32603,
          message: error.message
        },
        id
      };
    }
  }

  handleInitialize() {
    return {
      protocolVersion: '2024-11-05',
      capabilities: {
        tools: {}
      },
      serverInfo: {
        name: 'Circleback MCP Server',
        version: '1.0.0'
      }
    };
  }

  handleListTools() {
    return {
      tools: this.tools.map(tool => ({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.inputSchema
      }))
    };
  }

  async handleToolCall(params, accessToken) {
    const { name, arguments: args } = params;
    const tool = this.tools.find(t => t.name === name);

    if (!tool) {
      throw new Error(`Ferramenta não encontrada: ${name}`);
    }

    // Usar o token que o QuickSight mandou (já autenticado no Circleback)
    this.client.setToken(accessToken);

    const result = await tool.handler(args, this.client);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  }
}
