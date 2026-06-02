# Ferramentas MCP - Circleback Server

Documentação detalhada de cada ferramenta disponível no MCP Server.

## search_meetings

Pesquisa reuniões por palavra-chave, data, tags ou participantes.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Palavra-chave ou assunto da reunião"
    },
    "tag": {
      "type": "string",
      "description": "Filtrar por tag específica (opcional)"
    },
    "attendee": {
      "type": "string",
      "description": "Filtrar por participante (opcional)"
    },
    "startDate": {
      "type": "string",
      "description": "Data inicial (YYYY-MM-DD) (opcional)"
    },
    "endDate": {
      "type": "string",
      "description": "Data final (YYYY-MM-DD) (opcional)"
    },
    "limit": {
      "type": "number",
      "description": "Número máximo de resultados (padrão: 10)"
    }
  },
  "required": ["query"]
}
```

### Exemplos de Uso

```json
// Buscar reuniões sobre "sprint planning"
{
  "name": "search_meetings",
  "arguments": {
    "query": "sprint planning",
    "limit": 5
  }
}

// Buscar reuniões com participante específico em um período
{
  "name": "search_meetings",
  "arguments": {
    "query": "review",
    "attendee": "joao@empresa.com",
    "startDate": "2024-01-01",
    "endDate": "2024-03-31"
  }
}
```

---

## get_meeting_details

Obtém detalhes completos de uma reunião específica, incluindo resumo, participantes, action items e notas.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "meetingId": {
      "type": "string",
      "description": "ID da reunião"
    }
  },
  "required": ["meetingId"]
}
```

### Exemplo de Uso

```json
{
  "name": "get_meeting_details",
  "arguments": {
    "meetingId": "mtg_abc123xyz"
  }
}
```

---

## search_transcripts

Busca em transcrições de reuniões. Retorna trechos com timestamps, permitindo localizar exatamente quando algo foi dito.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Palavra-chave para buscar nas transcrições"
    },
    "meetingId": {
      "type": "string",
      "description": "ID da reunião específica (opcional)"
    },
    "limit": {
      "type": "number",
      "description": "Número máximo de resultados"
    }
  },
  "required": ["query"]
}
```

### Exemplos de Uso

```json
// Buscar menções a "deadline" em todas as transcrições
{
  "name": "search_transcripts",
  "arguments": {
    "query": "deadline",
    "limit": 10
  }
}

// Buscar em uma reunião específica
{
  "name": "search_transcripts",
  "arguments": {
    "query": "orçamento aprovado",
    "meetingId": "mtg_abc123xyz"
  }
}
```

---

## search_action_items

Encontra action items (tarefas/pendências) por palavra-chave, status ou assignee.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Palavra-chave para buscar"
    },
    "status": {
      "type": "string",
      "enum": ["pending", "done", "all"],
      "description": "Filtrar por status"
    },
    "limit": {
      "type": "number",
      "description": "Número máximo de resultados"
    }
  },
  "required": ["query"]
}
```

### Exemplos de Uso

```json
// Buscar action items pendentes sobre "deploy"
{
  "name": "search_action_items",
  "arguments": {
    "query": "deploy",
    "status": "pending"
  }
}

// Buscar todas as tarefas concluídas
{
  "name": "search_action_items",
  "arguments": {
    "query": "release",
    "status": "done",
    "limit": 20
  }
}
```

---

## search_emails

Pesquisa emails capturados pelo Circleback por palavra-chave, remetente ou destinatário.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Palavra-chave"
    },
    "sender": {
      "type": "string",
      "description": "Email do remetente (opcional)"
    },
    "recipient": {
      "type": "string",
      "description": "Email do destinatário (opcional)"
    },
    "limit": {
      "type": "number",
      "description": "Número máximo de resultados"
    }
  },
  "required": ["query"]
}
```

### Exemplos de Uso

```json
// Buscar emails sobre "proposta comercial"
{
  "name": "search_emails",
  "arguments": {
    "query": "proposta comercial",
    "limit": 5
  }
}

// Buscar emails de um remetente específico
{
  "name": "search_emails",
  "arguments": {
    "query": "contrato",
    "sender": "cliente@empresa.com"
  }
}
```

---

## find_profile

Procura uma pessoa pelo nome e retorna informações do perfil, incluindo histórico de interações.

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Nome da pessoa"
    }
  },
  "required": ["name"]
}
```

### Exemplo de Uso

```json
{
  "name": "find_profile",
  "arguments": {
    "name": "João Silva"
  }
}
```

---

## Protocolo MCP

As ferramentas são acessadas via JSON-RPC no endpoint `POST /mcp`.

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "search_meetings",
    "arguments": {
      "query": "sprint"
    }
  },
  "id": 1
}
```

### Response Format

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{ ... resultado JSON ... }"
      }
    ]
  },
  "id": 1
}
```

### Métodos Suportados

| Método | Descrição |
|--------|-----------|
| `initialize` | Retorna capabilities e versão do servidor |
| `tools/list` | Lista todas as ferramentas disponíveis |
| `tools/call` | Executa uma ferramenta específica |
