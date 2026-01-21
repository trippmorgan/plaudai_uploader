---
path: /home/server1/claude-team/mcp-server-standalone.mjs
type: service
updated: 2026-01-21
status: active
---

# mcp-server-standalone.mjs

## Purpose

MCP (Model Context Protocol) server that connects Claude Code instances to a team hub via WebSocket. Enables inter-Claude communication including asking questions, sharing updates, requesting code reviews, and checking team status.

## Exports

None (executable entry point)

## Dependencies

- @modelcontextprotocol/sdk/server/index.js (Server class)
- @modelcontextprotocol/sdk/server/stdio.js (StdioServerTransport)
- @modelcontextprotocol/sdk/types.js (CallToolRequestSchema, ListToolsRequestSchema)
- ws (WebSocket client)

## Used By

TBD

## Notes

- Connects to hub at `ws://100.124.78.58:4847` (Tailscale IP for tripp-hp-350-g2)
- Auto-reconnects on disconnect with 2-second delay
- Implements 4 MCP tools: `ask_team_claude`, `share_with_team`, `get_team_status`, `request_code_review`
- Uses pending queries Map to track async request/response pairs
- Identifies as `server1-claude-code` when connecting to hub