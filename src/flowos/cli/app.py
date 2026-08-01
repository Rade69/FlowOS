"""FlowOS CLI — Typer wrapper za interakciju sa FlowOS servisom.

Primarni tok:
    flowos session start --agent claude-code --task FLOW-42

CLI nikad ne piše direktno u SQLite. Koristi API ili offline JSONL spool
kada backend nije dostupan.
"""

import json
import os
import sys
from pathlib import Path

import typer

from flowos.cli.services.client import CliApiClient

app = typer.Typer(
    name="flowos",
    help="FlowOS CLI — lokalni lični operativni sistem za koordinaciju agentskih sesija",
    no_args_is_help=True,
)

# Pod-komande
project_app = typer.Typer(help="Upravljanje projektima")
task_app = typer.Typer(help="Upravljanje zadacima")
plan_app = typer.Typer(help="Plan i napredak")
session_app = typer.Typer(help="Sesije")

app.add_typer(project_app, name="project")
app.add_typer(task_app, name="task")
app.add_typer(plan_app, name="plan")
app.add_typer(session_app, name="session")


def _get_client() -> CliApiClient:
    """Kreira API klijenta sa automatskim otkrivanjem porta."""
    port = 9100
    runtime_file = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        / "FlowOS"
        / "runtime"
        / "service.json"
    )
    if runtime_file.exists():
        try:
            data = json.loads(runtime_file.read_text())
            port = data.get("port", 9100)
        except (json.JSONDecodeError, KeyError):
            pass
    return CliApiClient(base_url=f"http://127.0.0.1:{port}")


# ═══════════════════════════════════════════════════════════════════
# Root
# ═══════════════════════════════════════════════════════════════════


@app.callback()
def callback():
    """FlowOS CLI root."""


@app.command()
def version():
    """Prikaži verziju."""
    typer.echo("flowos 0.1.0")


@app.command()
def health():
    """Proveri da li je servis dostupan."""
    client = _get_client()
    try:
        resp = client.get("/health")
        typer.echo(f"✅ Servis dostupan na {client.base_url}")
        typer.echo(f"   Status: {resp.get('status', '?')}")
        typer.echo(f"   Uptime: {resp.get('uptime', 0):.0f}s")
    except Exception as e:
        typer.echo(f"❌ Servis nije dostupan: {e}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════
# Projekti
# ═══════════════════════════════════════════════════════════════════


@project_app.command("list")
def list_projects():
    """Prikaži sve projekte."""
    client = _get_client()
    try:
        projects = client.get("/projects")
        if not projects:
            typer.echo("Nema projekata.")
            return
        for p in projects:
            typer.echo(f"  {p['name']} — {p['repo_path']} [{p['status']}]")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


@project_app.command("create")
def create_project(
    name: str = typer.Option(..., "--name", "-n"), path: str = typer.Option(..., "--path", "-p")
):
    """Kreiraj novi projekat."""
    client = _get_client()
    try:
        p = client.post("/projects", {"name": name, "repo_path": path})
        typer.echo(f"✅ Projekat kreiran: {p['id']}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


@project_app.command("delete")
def delete_project(project_id: str = typer.Argument(...)):
    """Obriši projekat."""
    client = _get_client()
    try:
        client.delete(f"/projects/{project_id}")
        typer.echo(f"✅ Projekat obrisan: {project_id}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════
# Zadaci
# ═══════════════════════════════════════════════════════════════════


@task_app.command("list")
def list_tasks(project_id: str = typer.Option(..., "--project", "-p")):
    """Prikaži zadatke za projekat."""
    client = _get_client()
    try:
        tasks = client.get(f"/tasks?project_id={project_id}")
        if not tasks:
            typer.echo("Nema zadataka.")
            return
        for t in tasks:
            typer.echo(f"  {t['title']} [{t['status']}] {t['priority']}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


@task_app.command("create")
def create_task(
    project_id: str = typer.Option(..., "--project", "-p"),
    title: str = typer.Option(..., "--title", "-t"),
):
    """Kreiraj novi zadatak."""
    client = _get_client()
    try:
        t = client.post("/tasks", {"project_id": project_id, "title": title})
        typer.echo(f"✅ Zadatak kreiran: {t['id']}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════
# Plan
# ═══════════════════════════════════════════════════════════════════


@plan_app.command("progress")
def plan_progress(project_id: str = typer.Option(..., "--project", "-p")):
    """Prikaži napredak po planu za projekat."""
    client = _get_client()
    try:
        data = client.get(f"/projects/{project_id}/plan-progress")
        plan = data.get("plan")
        if not plan:
            typer.echo("Nema aktivnog plana.")
            return
        typer.echo(f"Plan: {plan['title']} [{plan['status']}]")
        typer.echo(
            f"Stavke: {data['total_items']} ukupno, {data['completed_items']} završeno, {data['blocked_items']} blokirano"
        )
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════
# Resume
# ═══════════════════════════════════════════════════════════════════


@app.command()
def resume(project_id: str = typer.Option(..., "--project", "-p")):
    """Prikaži 'Gde si stao' za projekat."""
    client = _get_client()
    try:
        data = client.get(f"/projects/{project_id}/resume")
        typer.echo(f"Status: {data.get('resume_status', '?')}")
        typer.echo(f"Pouzdanost: {data.get('confidence', '?')}")
        where = data.get("where_stopped", "")
        if where:
            typer.echo(f"Gde si stao: {where}")
        next_step = data.get("next_concrete_step", "")
        if next_step:
            typer.echo(f"Sledeći korak: {next_step}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════
# Sesije
# ═══════════════════════════════════════════════════════════════════


@session_app.command("start")
def session_start(
    agent: str = typer.Option(..., "--agent", "-a"),
    project: str = typer.Option(..., "--project", "-p"),
    repo: str = typer.Option(..., "--repo", "-r"),
    task: Optional[str] = typer.Option(None, "--task", "-t"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    worktree: Optional[str] = typer.Option(None, "--worktree", "-w"),
    plan_item: Optional[str] = typer.Option(None, "--plan-item"),
):
    """Pokreni novu agentsku sesiju."""
    client = _get_client()
    import os

    try:
        s = client.post("/sessions", {
            "project_id": project, "agent_type": agent, "repo_path": repo,
            "task_id": task, "model_name": model, "worktree_path": worktree,
            "plan_item_id": plan_item, "pid": os.getpid(),
        })
        typer.echo(f"✅ Sesija pokrenuta: {s['id']}")
        typer.echo(f"   Status: {s['status']}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


@session_app.command("end")
def session_end(
    session_id: str = typer.Argument(...),
    exit_code: Optional[int] = typer.Option(None, "--exit-code", "-e"),
):
    """Završi sesiju."""
    client = _get_client()
    try:
        body = {"exit_code": exit_code} if exit_code is not None else {}
        s = client.post(f"/sessions/{session_id}/end", body)
        typer.echo(f"✅ Sesija završena: {s['id']} ({s['status']})")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


@session_app.command("list")
def session_list(
    project: str = typer.Option(..., "--project", "-p"),
    active_only: bool = typer.Option(False, "--active"),
):
    """Prikaži sesije za projekat."""
    client = _get_client()
    try:
        path = f"/sessions/active?project_id={project}" if active_only else f"/sessions?project_id={project}"
        sessions = client.get(path)
        if not sessions:
            typer.echo("Nema sesija.")
            return
        for s in sessions:
            typer.echo(f"  {s['id'][:8]}... {s['agent_type']} [{s['status']}] {s.get('started_at', '')[:16]}")
    except Exception as e:
        typer.echo(f"Greška: {e}", err=True)
        raise typer.Exit(code=1)


# ═══════════════════════════════════════════════════════════════════


def main() -> int:
    try:
        app()
        return 0
    except Exception:
        typer.echo("Greška u FlowOS CLI-ju.", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
