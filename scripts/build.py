"""Build skripta za FlowOS MVP pakovanje (FLOW-406).

Koristi PyInstaller za pravljenje samostalnih .exe fajlova:
- flowos-service.exe (FastAPI backend)
- flowos-gui.exe (PySide6 GUI)
- flowos.exe (Typer CLI wrapper)

Pokretanje: python scripts/build.py
Izlaz: dist/
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def run_pyinstaller(name: str, entry: str, hidden_imports: list[str] | None = None) -> bool:
    """Pokreće PyInstaller za jedan ulazni fajl."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--console",
        f"--name={name}",
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build" / name),
        "--specpath",
        str(ROOT),
    ]
    if hidden_imports:
        for hi in hidden_imports:
            cmd.extend(["--hidden-import", hi])
    cmd.append(str(ROOT / entry))

    print(f"  {name}: {entry}")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
    return result.returncode == 0


def main() -> int:
    print("FlowOS — build MVP")
    print(f"  Root: {ROOT}")
    print(f"  Dist: {DIST}")

    DIST.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)

    targets = [
        (
            "flowos-service",
            "src/flowos/service/app.py",
            [
                "sqlalchemy",
                "alembic",
                "fastapi",
                "uvicorn",
                "flowos.service.services.infrastructure.persistence",
            ],
        ),
        (
            "flowos-gui",
            "src/flowos/gui/app.py",
            [
                "PySide6",
                "flowos.gui.views",
                "flowos.gui.controllers",
                "flowos.gui.services",
                "flowos.gui.theme",
            ],
        ),
        (
            "flowos",
            "src/flowos/cli/app.py",
            [
                "typer",
                "httpx",
            ],
        ),
    ]

    failed = 0
    for name, entry, imports in targets:
        if not Path(ROOT / entry).exists():
            print(f"  [SKIP] {name} — {entry} ne postoji")
            continue
        ok = run_pyinstaller(name, entry, imports)
        if not ok:
            failed += 1
            print(f"  [FAIL] {name}")

    if failed:
        print(f"\n[FAIL] {failed} build-a nije uspelo")
        return 1

    # Kopiraj alembic folder pored servisa
    import shutil

    alembic_dest = DIST / "alembic"
    if alembic_dest.exists():
        shutil.rmtree(alembic_dest)
    shutil.copytree(
        ROOT / "alembic", alembic_dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )

    print(f"\n[PASS] Build završen — {DIST}")
    for exe in DIST.glob("*.exe"):
        print(f"  {exe.name} ({exe.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
