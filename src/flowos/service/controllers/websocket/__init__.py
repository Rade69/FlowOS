"""WebSocket Controllers — WebSocket endpointi.

GUI dobija promene uživo preko jednog WebSocket kanala.
Envelope: { schema_version, event_id, type, occurred_at, project_id, payload }.
Nakon reconnecta GUI poziva REST refresh — WebSocket nije izvor istine.
"""
