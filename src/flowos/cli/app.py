"""FlowOS CLI — Typer wrapper za registraciju sesija.

Primarni tok:
    flowos session start --agent claude-code --task FLOW-42

CLI nikad ne piše direktno u SQLite. Koristi API ili offline JSONL spool
kada backend nije dostupan.
"""

import sys

import typer

app = typer.Typer(
    name="flowos",
    help="FlowOS CLI — lokalni lični operativni sistem za koordinaciju agentskih sesija",
    no_args_is_help=True,
)


@app.callback()
def callback() -> None:
    """FlowOS CLI root."""


@app.command()
def version() -> None:
    """Prikaži verziju FlowOS CLI-ja."""
    typer.echo("flowos 0.1.0")


def main() -> int:
    """Glavna ulazna tačka za flowos.exe."""
    try:
        app()
        return 0
    except Exception:
        typer.echo("Greška u FlowOS CLI-ju.", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
