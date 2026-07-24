from typing import List, Dict, Any
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections and broadcasting."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_data: Dict[str, Dict] = {}  # Store additional data per connection
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if client_id:
            self.connection_data[client_id] = {
                "websocket": websocket,
                "connected_at": datetime.utcnow()
            }
        
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from connection data
        for client_id, data in list(self.connection_data.items()):
            if data["websocket"] == websocket:
                del self.connection_data[client_id]
                break
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all active connections."""
        if not self.active_connections:
            logger.debug("No active WebSocket connections to broadcast to")
            return
        
        disconnected = []
        
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
        
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected clients")
    
    async def broadcast_status_update(self, device_id: str, status: str, 
                                      diagnostic: Dict[str, Any]):
        """Broadcast a device status update."""
        await self.broadcast({
            "type": "STATUS_UPDATE",
            "device_id": device_id,
            "status": status,
            "diagnostic": diagnostic,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    async def broadcast_alert(self, device_id: str, hostname: str, 
                             ip_address: str, diagnostic: Dict[str, Any],
                             ticket_id: str):
        """Broadcast a new alert."""
        await self.broadcast({
            "type": "ALERT",
            "device_id": device_id,
            "hostname": hostname,
            "ip_address": ip_address,
            "diagnostic": diagnostic,
            "ticket_id": ticket_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

# Import datetime for use in methods
from datetime import datetime

# Global singleton instance used across the app
websocket_manager = WebSocketManager()
