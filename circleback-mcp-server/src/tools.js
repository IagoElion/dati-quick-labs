export const tools = [
  {
    name: 'search_meetings',
    description: 'Pesquisa reuniões por palavra-chave, data, tags, participantes',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave ou assunto da reunião'
        },
        tag: {
          type: 'string',
          description: 'Filtrar por tag específica (opcional)'
        },
        attendee: {
          type: 'string',
          description: 'Filtrar por participante (opcional)'
        },
        startDate: {
          type: 'string',
          description: 'Data inicial (YYYY-MM-DD) (opcional)'
        },
        endDate: {
          type: 'string',
          description: 'Data final (YYYY-MM-DD) (opcional)'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados (padrão: 10)'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchMeetings(args.query, {
        tag: args.tag,
        attendee: args.attendee,
        startDate: args.startDate,
        endDate: args.endDate,
        limit: args.limit
      });
    }
  },

  {
    name: 'get_meeting_details',
    description: 'Obtém detalhes completos de uma reunião específica',
    inputSchema: {
      type: 'object',
      properties: {
        meetingId: {
          type: 'string',
          description: 'ID da reunião'
        }
      },
      required: ['meetingId']
    },
    handler: async (args, client) => {
      return client.getMeeting(args.meetingId);
    }
  },

  {
    name: 'search_transcripts',
    description: 'Busca em transcrições de reuniões com timestamps',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave para buscar nas transcrições'
        },
        meetingId: {
          type: 'string',
          description: 'ID da reunião específica (opcional)'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchTranscripts(args.query, {
        meetingId: args.meetingId,
        limit: args.limit
      });
    }
  },

  {
    name: 'search_action_items',
    description: 'Encontra action items por palavra-chave, status ou assignee',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave para buscar'
        },
        status: {
          type: 'string',
          enum: ['pending', 'done', 'all'],
          description: 'Filtrar por status'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchActionItems(args.query, {
        status: args.status,
        limit: args.limit
      });
    }
  },

  {
    name: 'search_emails',
    description: 'Pesquisa emails por palavra-chave, remetente ou destinatário',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Palavra-chave'
        },
        sender: {
          type: 'string',
          description: 'Email do remetente (opcional)'
        },
        recipient: {
          type: 'string',
          description: 'Email do destinatário (opcional)'
        },
        limit: {
          type: 'number',
          description: 'Número máximo de resultados'
        }
      },
      required: ['query']
    },
    handler: async (args, client) => {
      return client.searchEmails(args.query, {
        sender: args.sender,
        recipient: args.recipient,
        limit: args.limit
      });
    }
  },

  {
    name: 'find_profile',
    description: 'Procura uma pessoa pelo nome e obtém seu perfil',
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Nome da pessoa'
        }
      },
      required: ['name']
    },
    handler: async (args, client) => {
      return client.findProfile(args.name);
    }
  }
];
