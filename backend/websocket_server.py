"""
=============================================================================
WEBSOCKET SERVER
=============================================================================

Real-time communication for ORCC

Message Types:
    - patient_selected: Patient context changed
    - procedure_update: Procedure status changed
    - task_update: Task created/updated/completed
    - fact_added: New clinical fact extracted
    - prompt_update: Coding prompt created/resolved
    - sync_request: Request full state sync

=============================================================================
"""
import json
import logging
from datetime import datetime
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.
    """

    def __init__(self):
        # Active connections by client ID
        self.active_connections: Dict[str, WebSocket] = {}
        # Connections subscribed to specific patients (by MRN)
        self.patient_subscriptions: Dict[str, Set[str]] = {}
        # Connections subscribed to specific cases
        self.case_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id} (total: {len(self.active_connections)})")

    def disconnect(self, client_id: str) -> None:
        """Remove a disconnected client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from all subscriptions
        for patient_mrn, clients in list(self.patient_subscriptions.items()):
            clients.discard(client_id)
            if not clients:
                del self.patient_subscriptions[patient_mrn]

        for case_id, clients in list(self.case_subscriptions.items()):
            clients.discard(client_id)
            if not clients:
                del self.case_subscriptions[case_id]

        logger.info(f"WebSocket disconnected: {client_id} (remaining: {len(self.active_connections)})")

    def subscribe_to_patient(self, client_id: str, mrn: str) -> None:
        """Subscribe a client to updates for a specific patient."""
        if mrn not in self.patient_subscriptions:
            self.patient_subscriptions[mrn] = set()
        self.patient_subscriptions[mrn].add(client_id)
        logger.debug(f"Client {client_id} subscribed to patient {mrn}")

    def subscribe_to_case(self, client_id: str, case_id: str) -> None:
        """Subscribe a client to updates for a specific case."""
        if case_id not in self.case_subscriptions:
            self.case_subscriptions[case_id] = set()
        self.case_subscriptions[case_id].add(client_id)
        logger.debug(f"Client {client_id} subscribed to case {case_id}")

    async def send_personal_message(self, message: Dict[str, Any], client_id: str) -> None:
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    async def broadcast_to_patient_subscribers(self, mrn: str, message: Dict[str, Any]) -> None:
        """Broadcast to clients subscribed to a specific patient."""
        if mrn not in self.patient_subscriptions:
            return

        disconnected = []
        for client_id in self.patient_subscriptions[mrn]:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to patient subscriber {client_id}: {e}")
                    disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    async def broadcast_to_case_subscribers(self, case_id: str, message: Dict[str, Any]) -> None:
        """Broadcast to clients subscribed to a specific case."""
        if case_id not in self.case_subscriptions:
            return

        disconnected = []
        for client_id in self.case_subscriptions[case_id]:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to case subscriber {client_id}: {e}")
                    disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "patient_subscriptions": len(self.patient_subscriptions),
            "case_subscriptions": len(self.case_subscriptions),
            "client_ids": list(self.active_connections.keys())
        }


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
    """
    Main WebSocket endpoint handler.

    Accepts connections and processes incoming messages.
    """
    # Generate client ID if not provided
    if not client_id:
        client_id = f"client_{datetime.utcnow().timestamp()}"

    await manager.connect(websocket, client_id)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        while True:
            # Receive and process messages
            data = await websocket.receive_json()
            await handle_message(client_id, data)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


async def handle_message(client_id: str, data: Dict[str, Any]) -> None:
    """
    Handle incoming WebSocket messages.

    Message format:
    {
        "type": "message_type",
        "payload": { ... }
    }
    """
    msg_type = data.get("type", "unknown")
    payload = data.get("payload", {})

    logger.debug(f"Received {msg_type} from {client_id}")

    if msg_type == "subscribe_patient":
        # Subscribe to patient updates
        mrn = payload.get("mrn")
        if mrn:
            manager.subscribe_to_patient(client_id, mrn)
            await manager.send_personal_message({
                "type": "subscribed",
                "resource": "patient",
                "mrn": mrn
            }, client_id)

    elif msg_type == "subscribe_case":
        # Subscribe to case updates
        case_id = payload.get("case_id")
        if case_id:
            manager.subscribe_to_case(client_id, case_id)
            await manager.send_personal_message({
                "type": "subscribed",
                "resource": "case",
                "case_id": case_id
            }, client_id)

    elif msg_type == "patient_selected":
        # Broadcast patient selection to all clients
        await manager.broadcast({
            "type": "patient_selected",
            "mrn": payload.get("mrn"),
            "patient_name": payload.get("patient_name"),
            "source": client_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    elif msg_type == "procedure_update":
        # Broadcast procedure status change
        message = {
            "type": "procedure_update",
            "procedure_id": payload.get("procedure_id"),
            "status": payload.get("status"),
            "changes": payload.get("changes", {}),
            "source": client_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        # Broadcast to patient subscribers if MRN available
        mrn = payload.get("mrn")
        if mrn:
            await manager.broadcast_to_patient_subscribers(mrn, message)
        else:
            await manager.broadcast(message)

    elif msg_type == "task_update":
        # Broadcast task update
        message = {
            "type": "task_update",
            "task_id": payload.get("task_id"),
            "action": payload.get("action"),  # created, updated, completed, deleted
            "task": payload.get("task"),
            "source": client_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        mrn = payload.get("mrn")
        if mrn:
            await manager.broadcast_to_patient_subscribers(mrn, message)
        else:
            await manager.broadcast(message)

    elif msg_type == "fact_added":
        # Broadcast new fact
        case_id = payload.get("case_id")
        message = {
            "type": "fact_added",
            "case_id": case_id,
            "fact_type": payload.get("fact_type"),
            "value": payload.get("value"),
            "source": client_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        if case_id:
            await manager.broadcast_to_case_subscribers(case_id, message)

    elif msg_type == "prompt_update":
        # Broadcast prompt change
        case_id = payload.get("case_id")
        message = {
            "type": "prompt_update",
            "case_id": case_id,
            "prompt_id": payload.get("prompt_id"),
            "action": payload.get("action"),  # created, resolved, snoozed, dismissed
            "source": client_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        if case_id:
            await manager.broadcast_to_case_subscribers(case_id, message)

    elif msg_type == "sync_request":
        # Client requesting full state sync
        await manager.send_personal_message({
            "type": "sync_response",
            "message": "Sync functionality not yet implemented",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, client_id)

    elif msg_type == "ping":
        # Keepalive ping
        await manager.send_personal_message({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, client_id)

    else:
        logger.warning(f"Unknown message type: {msg_type}")


# Utility functions for other modules to send notifications

async def notify_patient_update(mrn: str, update_type: str, data: Dict[str, Any]) -> None:
    """Send notification about a patient update."""
    await manager.broadcast_to_patient_subscribers(mrn, {
        "type": f"patient_{update_type}",
        "mrn": mrn,
        "data": data,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


async def notify_task_created(task: Dict[str, Any]) -> None:
    """Send notification about new task."""
    await manager.broadcast({
        "type": "task_update",
        "action": "created",
        "task": task,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


async def notify_fact_extracted(case_id: str, facts: list) -> None:
    """Send notification about extracted facts."""
    await manager.broadcast_to_case_subscribers(case_id, {
        "type": "facts_extracted",
        "case_id": case_id,
        "facts_count": len(facts),
        "facts": facts,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


async def notify_prompt_created(case_id: str, prompt: Dict[str, Any]) -> None:
    """Send notification about new coding prompt."""
    await manager.broadcast_to_case_subscribers(case_id, {
        "type": "prompt_update",
        "action": "created",
        "case_id": case_id,
        "prompt": prompt,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
