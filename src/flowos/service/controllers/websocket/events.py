"""WebSocket endpoint — Controller-nivo ruta i auth provjera.

EventBus pub/sub je premješten u services.infrastructure.events (FLOW-1158);
ovdje ostaju samo Controller-specifični dijelovi: ws_endpoint() (FastAPI
WebSocket ruta) i _is_authorized() (auth provjera). EventBus/event_bus se
re-eksportuju radi kompatibilnosti composition_root-a.
"""

from fastapi import WebSocket

from flowos.service.services.infrastructure.events import EventBus, event_bus
from flowos.service.services.infrastructure.runtime import verify_bearer_token

__all__ = ["EventBus", "event_bus", "ws_endpoint"]


def _is_authorized(ws: WebSocket) -> bool:
    """FLOW-1107: konekcija mora posjedovati trenutni instance token.

    Isti `verify_bearer_token()` primitiv kao HTTP middleware — jedan
    autoritativan način provjere, ne odvojena WS-specifična logika.
    """
    runtime_mgr = getattr(ws.app.state, "runtime", None)
    expected = getattr(runtime_mgr, "token", None) if runtime_mgr is not None else None
    return verify_bearer_token(expected, ws.headers.get("authorization"))


async def ws_endpoint(ws: WebSocket):
    """WebSocket endpoint — prima konekcije i drži ih otvorenim.

    Auth se provjerava PRIJE `accept()` — bez validnog tokena konekcija se
    nikad ne pretvara u aktivan FlowOS event klijent.
    """
    if not _is_authorized(ws):
        await ws.close(code=4401)
        return

    await event_bus.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        event_bus.disconnect(ws)
