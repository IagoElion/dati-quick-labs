import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const TIFLUX_BASE = "https://api.tiflux.com/api/v2";
const TOKEN = process.env.TIFLUX_TOKEN;

if (!TOKEN) {
  console.error("ERROR: Set TIFLUX_TOKEN environment variable");
  process.exit(1);
}

async function tifluxFetch(path, options = {}) {
  const { method = "GET", body, params = {} } = options;

  let url = `${TIFLUX_BASE}${path}`;
  const queryString = new URLSearchParams(params).toString();
  if (queryString) url += `?${queryString}`;

  const fetchOptions = {
    method,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
    },
  };

  if (body) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(body);
  }

  const res = await fetch(url, fetchOptions);
  const text = await res.text();

  if (!res.ok) {
    throw new Error(`Tiflux API ${res.status}: ${text}`);
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// ── Server setup ──────────────────────────────────────────────
const server = new McpServer(
  { name: "tiflux", version: "1.0.0" },
  {
    instructions:
      "Tiflux helpdesk integration. Use list_tickets to browse tickets, get_ticket for details, create_ticket to open new ones. Clients and desks endpoints also available.",
  }
);

// ── LIST TICKETS ──────────────────────────────────────────────
server.tool(
  "list_tickets",
  "List tickets from Tiflux. Returns all tickets (API does not support query params for filtering).",
  {},
  async () => {
    try {
      const data = await tifluxFetch("/tickets");
      const summary = Array.isArray(data)
        ? data.map((t) => ({
            ticket_number: t.ticket_number,
            title: t.title,
            client: t.client?.name,
            desk: t.desk?.name,
            status: t.status?.name,
            stage: t.stage?.name,
            priority: t.priority?.name,
            responsible: t.responsible?.name || "Unassigned",
            created_at: t.created_at,
            is_closed: t.is_closed,
          }))
        : data;
      return { content: [{ type: "text", text: JSON.stringify(summary, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── GET TICKET ────────────────────────────────────────────────
server.tool(
  "get_ticket",
  "Get a specific ticket by ticket number",
  { ticket_number: z.number().describe("The ticket number") },
  async ({ ticket_number }) => {
    try {
      const data = await tifluxFetch(`/tickets/${ticket_number}`);
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── CREATE TICKET ─────────────────────────────────────────────
server.tool(
  "create_ticket",
  "Create a new ticket in Tiflux",
  {
    title: z.string().describe("Ticket title"),
    client_id: z.number().describe("Client ID"),
    desk_id: z.number().describe("Desk ID"),
    description: z.string().optional().describe("Ticket description"),
    priority_id: z.number().optional().describe("Priority ID"),
    responsible_id: z.number().optional().describe("Responsible user ID"),
    requestor_name: z.string().optional().describe("Requestor name"),
    requestor_email: z.string().optional().describe("Requestor email"),
  },
  async (params) => {
    try {
      const body = {
        title: params.title,
        client_id: params.client_id,
        desk_id: params.desk_id,
      };
      if (params.description) body.description = params.description;
      if (params.priority_id) body.priority_id = params.priority_id;
      if (params.responsible_id) body.responsible_id = params.responsible_id;
      if (params.requestor_name || params.requestor_email) {
        body.requestor = {};
        if (params.requestor_name) body.requestor.name = params.requestor_name;
        if (params.requestor_email) body.requestor.email = params.requestor_email;
      }
      const data = await tifluxFetch("/tickets", { method: "POST", body });
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── UPDATE TICKET ─────────────────────────────────────────────
server.tool(
  "update_ticket",
  "Update an existing ticket",
  {
    ticket_number: z.number().describe("The ticket number to update"),
    title: z.string().optional().describe("New title"),
    priority_id: z.number().optional().describe("New priority ID"),
    responsible_id: z.number().optional().describe("New responsible user ID"),
    stage_id: z.number().optional().describe("New stage ID"),
    status_id: z.number().optional().describe("New status ID"),
  },
  async ({ ticket_number, ...updates }) => {
    try {
      const body = {};
      Object.entries(updates).forEach(([k, v]) => {
        if (v !== undefined) body[k] = v;
      });
      const data = await tifluxFetch(`/tickets/${ticket_number}`, { method: "PUT", body });
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── CLOSE TICKET ──────────────────────────────────────────────
server.tool(
  "close_ticket",
  "Close a ticket",
  { ticket_number: z.number().describe("The ticket number to close") },
  async ({ ticket_number }) => {
    try {
      const data = await tifluxFetch(`/tickets/${ticket_number}/close`, { method: "POST" });
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── LIST CLIENTS ──────────────────────────────────────────────
server.tool(
  "list_clients",
  "List all clients from Tiflux",
  {},
  async () => {
    try {
      const data = await tifluxFetch("/clients");
      const summary = Array.isArray(data)
        ? data.map((c) => ({
            id: c.id,
            name: c.name,
            social: c.social,
            social_revenue: c.social_revenue,
            status: c.status,
          }))
        : data;
      return { content: [{ type: "text", text: JSON.stringify(summary, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── GET CLIENT ────────────────────────────────────────────────
server.tool(
  "get_client",
  "Get a specific client by ID",
  { client_id: z.number().describe("The client ID") },
  async ({ client_id }) => {
    try {
      const data = await tifluxFetch(`/clients/${client_id}`);
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── LIST DESKS ────────────────────────────────────────────────
server.tool(
  "list_desks",
  "List all desks (service queues) from Tiflux",
  {},
  async () => {
    try {
      const data = await tifluxFetch("/desks");
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── ADD COMMUNICATION ─────────────────────────────────────────
server.tool(
  "add_communication",
  "Add an internal communication/note to a ticket",
  {
    ticket_number: z.number().describe("The ticket number"),
    content: z.string().describe("Communication content (HTML supported)"),
    is_internal: z.boolean().optional().default(true).describe("Internal note (true) or public reply (false)"),
  },
  async ({ ticket_number, content, is_internal }) => {
    try {
      const body = { content, is_internal: is_internal ?? true };
      const data = await tifluxFetch(`/tickets/${ticket_number}/communications`, {
        method: "POST",
        body,
      });
      return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${e.message}` }], isError: true };
    }
  }
);

// ── Start server ──────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
