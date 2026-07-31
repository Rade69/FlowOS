"""FlowOS Infrastructure — interne implementacije Services sloja.

Ovo nije četvrti arhitektonski sloj — to su tehničke implementacije
koje koristi Services sloj:
- persistence/: SQLAlchemy modeli, session factory, migracije
- filesystem/: operacije nad fajlovima i direktorijumima
- process/: Windows Job Objects, subprocess management
- agent_adapters/: Claude Code, pi, Codex, Generic adapteri

Infrastructure moduli se ne smeju pozivati iz View-a ili Controller-a.
"""
