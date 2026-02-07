from fastapi import WebSocket
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Store active connections: shop_id -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, shop_id: str):
        await websocket.accept()
        if shop_id not in self.active_connections:
            self.active_connections[shop_id] = []
        self.active_connections[shop_id].append(websocket)
        logger.info(f"WebSocket connected for shop {shop_id}. Total connections: {len(self.active_connections[shop_id])}")

    def disconnect(self, websocket: WebSocket, shop_id: str):
        if shop_id in self.active_connections:
            if websocket in self.active_connections[shop_id]:
                self.active_connections[shop_id].remove(websocket)
                if not self.active_connections[shop_id]:
                    del self.active_connections[shop_id]
        logger.info(f"WebSocket disconnected for shop {shop_id}")

    async def broadcast(self, shop_id: str, message: dict):
        if shop_id in self.active_connections:
            # Copy list to avoid concurrent modification issues during iteration
            for connection in list(self.active_connections[shop_id]):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to shop {shop_id}: {e}")
                    # Remove dead connection
                    self.disconnect(connection, shop_id)

manager = ConnectionManager()
