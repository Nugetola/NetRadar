"""
WebSocket API endpoint for OIC NetRadar.
Handles real-time client connections for status updates and alerts.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    client_id = None

    try:
        # Accept connection
        await websocket_manager.connect(websocket)

        # Send initial connection confirmation as JSON
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to NetRadar WebSocket",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        # Listen for messages from client
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                msg_type = message.get("type")

                if msg_type == "PING":
                    # Respond to client heartbeat/ping
                    await websocket.send_json({
                        "type": "PONG",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })

                elif msg_type == "IDENTIFY":
                    # Optional: client identifies itself (e.g. agent_id)
                    client_id = message.get("client_id")
                    logger.info(f"Client identified: {client_id}")

                else:
                    logger.debug(f"Received unhandled message type: {msg_type}")

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON over WebSocket")
                await websocket.send_json({
                    "type": "ERROR",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
        logger.info(f"Client disconnected (client_id={client_id})")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        websocket_manager.disconnect(websocket)