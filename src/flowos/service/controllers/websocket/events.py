"""WebSocket menadžer — emituje događaje povezanim GUI klijentima.

Podržava:
- service.ready
- session.updated/completed
- conflict.created
- reconciliation.created
- plan_progress.updated
- project.resume.updated
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("flowos.websocket")


class EventBus:
    """Simple pub/sub za WebSocket događaje."""

    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info("WebSocket klijent povezan (ukupno: %d)", len(self._connections))

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info("WebSocket klijent isključen (ukupno: %d)", len(self._connections))

    async def emit(self, event_type: str, payload: dict[str, Any]):
        """Emituje događaj svim povezanim klijentima."""
        envelope = {
            "schema_version": 1,
            "type": event_type,
            "payload": payload,
        }
        raw = json.dumps(envelope, default=str)
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(raw)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)


# Globalni event bus — jedan po procesu
event_bus = EventBus()


async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint — prima konekcije i drži ih otvorenim."""
    await event_bus.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        event_bus.disconnect(ws)
