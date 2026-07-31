# FlowOS

Lokalni lični operativni sistem za koordinaciju agentskih sesija.

FlowOS prati i koordiniše paralelne agentske sesije (Claude Code, Codex, pi) u dijeljenim Git working treejima — detektuje konflikte, pripisuje promjene, upravlja worktree izolacijom i vodi evidenciju o tome ko radi šta.

## Stack

- **GUI:** Python 3.12 + PySide6 + Qt Widgets
- **Backend:** FastAPI (lokalni servis, sluša samo na 127.0.0.1)
- **CLI:** Typer wrapper za registraciju sesija
- **Baza:** SQLite, WAL režim
- **Platforma:** Windows 10/11

## Razvoj

```powershell
# Instalacija
pip install -e ".[dev]"

# Pokretanje servisa
python scripts/run_service.py

# Pokretanje GUI-ja
python scripts/run_gui.py

# CLI
flowos version

# Verifikacija (format, lint, typecheck, testovi, architecture)
python scripts/verify.py
```

## Dokumentacija

- [CLAUDE.md](./CLAUDE.md) — pravila rada za AI agente
- [AGENTS.md](./AGENTS.md) — obavezna pravila za sve agente
- [FlowOS-novi-detaljan-plan-PySide6.md](./FlowOS-novi-detaljan-plan-PySide6.md) — kompletan plan realizacije
- [FlowOS-kompletan-plan.md](./FlowOS-kompletan-plan.md) — originalni arhitektonski plan
- [project_rooms/](./project_rooms/) — planovi za HIGH/CRITICAL izmjene
- [agent_reports/](./agent_reports/) — izvještaji agentskih sesija

## Arhitektura

```
flowos-gui.exe          (PySide6)
    ↓ HTTP/WebSocket
flowos-service.exe      (FastAPI)
    ↓ subprocess/JobObject
Claude Code | Codex | pi | CLI

flowos.exe              (Typer CLI wrapper)
```

View → Controller → Services troslojna arhitektura.
Stroge granice između slojeva — kršenje ruši `verify.py`.

## Licence

MIT