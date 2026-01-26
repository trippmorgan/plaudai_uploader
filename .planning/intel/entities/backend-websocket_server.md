---
path: /home/server1/plaudai_uploader/backend/websocket_server.py
type: service
updated: 2026-01-25
status: active
---

# websocket_server.py

## Purpose

Provides real-time bidirectional communication for the ORCC system via WebSockets. Manages client connections with subscription-based routing to patient MRNs and case IDs. Broadcasts updates for patient selection, procedure status changes, task updates, fact extraction events, and coding prompt notifications to relevant subscribers.

## Exports

- `ConnectionManager` - Class managing WebSocket connections and subscriptions
- `manager` - Global singleton instance of ConnectionManager
- `websocket_endpoint(websocket, client_id)` - Main WebSocket handler for client connections
- `handle_message(client_id, data)` - Processes incoming WebSocket messages
- `notify_patient_update(mrn, update_type, data)` - Utility to broadcast patient updates
- `notify_task_created(task)` - Utility to broadcast new task notifications
- `notify_fact_extracted(case_id, facts)` - Utility to broadcast fact extraction events
- `notify_prompt_created(case_id, prompt)` - Utility to broadcast coding prompt notifications

## Dependencies

- fastapi - WebSocket support and disconnect handling
- json - Message serialization

## Used By

TBD

## Notes

Supports message types: patient_selected, procedure_update, task_update, fact_added, prompt_update, sync_request, and ping/pong keepalive. Clients can subscribe to specific patient MRNs or case IDs to receive targeted updates.
