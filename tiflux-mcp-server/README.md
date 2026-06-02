# Tiflux MCP Server

MCP Server local que conecta à API v2 do Tiflux.

## Instalação

1. Copie esta pasta para um local permanente (ex: `C:\Users\Dati\tiflux-mcp-server`)
2. Abra o terminal nessa pasta e rode:

```bash
npm install
```

## Configuração no Amazon Quick

Vá em **Settings → Capabilities → MCP → "+ Add MCP server"**:

- **Tipo**: Local (stdio)
- **Command**: `node`
- **Args**: `C:\Users\Dati\tiflux-mcp-server\index.js`
- **Environment Variables**:
  - `TIFLUX_TOKEN` = `seu_token_aqui`

## Tools disponíveis

| Tool | Descrição |
|------|-----------|
| `list_tickets` | Lista todos os tickets |
| `get_ticket` | Detalhes de um ticket específico |
| `create_ticket` | Cria novo ticket |
| `update_ticket` | Atualiza ticket existente |
| `close_ticket` | Fecha um ticket |
| `list_clients` | Lista todos os clientes |
| `get_client` | Detalhes de um cliente |
| `list_desks` | Lista mesas de serviço |
| `add_communication` | Adiciona comunicação a um ticket |
