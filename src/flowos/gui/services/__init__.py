"""FlowOS GUI Services — komunikacija sa backendom.

GUI Services su jedini sloj koji sme da koristi mrežu (HTTP, WebSocket).
Ne znaju ništa o konkretnim widgetima, prozorima ili Qt signalima.
Mapiraju transportne greške u domenske izuzetke.
"""

from flowos.gui.services.client import GuiApiClient

__all__ = ["GuiApiClient"]
