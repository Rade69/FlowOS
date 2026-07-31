"""CLI View — formatirani izlaz za terminal.

Standardni format na kraju svakog zadatka:
    STATUS: OK | PARCIJALNO | BLOKIRANO
    IZMIJENJENI FAJLOVI: lista
    ŠTA JE URAĐENO: kratko
    ŠTA NIJE URAĐENO: (ako postoji)
    PITANJA: (ako postoje)
"""

import typer


def print_result(
    status: str,
    changed_files: list[str] | None = None,
    summary: str | None = None,
    missing: str | None = None,
    questions: str | None = None,
) -> None:
    """Štampa standardni završni output."""
    typer.echo(f"STATUS: {status}")
    if changed_files:
        typer.echo(f"IZMIJENJENI FAJLOVI: {', '.join(changed_files)}")
    if summary:
        typer.echo(f"ŠTA JE URAĐENO: {summary}")
    if missing:
        typer.echo(f"ŠTA NIJE URAĐENO: {missing}")
    if questions:
        typer.echo(f"PITANJA: {questions}")


def print_error(message: str) -> None:
    """Štampa grešku na stderr."""
    typer.echo(f"GREŠKA: {message}", err=True)
