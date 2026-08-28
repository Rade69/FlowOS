"""Infrastrukturni pub/sub za WebSocket događaje (FLOW-1158).

EventBus je infrastrukturni objekat koji smiju importovati i Services i
Controllers sloj. Izdvojen je iz controllers/websocket/events.py da Services
ne bi uvozili iz Controller paketa. Controller-specifični dijelovi
(ws_endpoint, auth provjera) ostaju u controllers/websocket/events.py, koji
ovaj modul re-eksportuje.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("flowos.websocket")


class EventBus:
    """Pub/sub za WebSocket događaje sa threadsafe emit podrškom."""

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Veže event bus za glavni asyncio event loop.

        Mora se pozvati tokom lifespan startup-a, dok je loop aktivan.
        """
        self._loop = loop
        logger.info("EventBus vezan za glavni event loop")

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

    def emit_sync(self, event_type: str, payload: dict[str, Any]):
        """Threadsafe emit — može se pozvati iz sync worker thread-ova.

        Koristi run_coroutine_threadsafe za slanje u glavni event loop.
        Ako loop nije bindovan (npr. pre startup-a), događaj se gubi
        uz upozorenje.
        """
        if self._loop is None:
            logger.warning("EventBus nema bindovan loop — događaj %s odbačen", event_type)
            return

        if not self._connections:
            return

        asyncio.run_coroutine_threadsafe(
            self.emit(event_type, payload),
            self._loop,
        )


# Globalni event bus — jedan po procesu
event_bus = EventBus()
