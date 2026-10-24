import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class NotificationConnectionManager:
    """Tracks open notification sockets per user (a user may have several tabs/devices).

    Connections live in this process's memory, so pushes only reach sockets held by
    the same process. That's fine for a single uvicorn worker; running several
    workers would need a shared broker such as Redis pub/sub.
    """

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    def connect(self, websocket: WebSocket, user_id: int):
        self.active_connections.setdefault(user_id, set()).add(websocket)
        logger.info("User %s connected to notifications socket", user_id)

    def disconnect(self, websocket: WebSocket, user_id: int):
        connections = self.active_connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self.active_connections[user_id]
        logger.info("User %s disconnected from notifications socket", user_id)

    async def send_to_user(self, user_id: int, message: dict):
        """Send a message to every open socket for the user, dropping dead ones."""
        for websocket in list(self.active_connections.get(user_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(websocket, user_id)


notification_manager = NotificationConnectionManager()
