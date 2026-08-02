#!python
# ruff: noqa: T201
"""FlowOS standardna verifikaciona skripta.

Pokreće sve provere redom:
1. ruff format --check    (formatiranje)
2. ruff check             (lint)
3. mypy                   (type checking)
4. architecture tests     (granice slojeva)
5. unit + integracijski testovi

Svaka provera se izvršava; ne staje na prvoj grešci.
Exit code 0 samo ako sve provere prolaze.

Koristi se:
- ručno: python scripts/verify.py
- iz wrapper-a na kraju sesije
- iz Managed/Durable toka kao VERIFY korak
"""

import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed: bool | None = None
        self.output: str = ""
        self.exit_code: int = -1


def run_step(name: str, cmd: list[str]) -> Result:
    """Pokreće jedan korak verifikacije i vraća Result."""
    result = Result(name)
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"  {' '.join(cmd)}")
    print(f"{'=' * 60}")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        result.exit_code = proc.returncode
        result.output = (proc.stdout or "") + (proc.stderr or "")
        result.passed = proc.returncode == 0

        if proc.stdout:
            print(proc.stdout)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)

    except FileNotFoundError:
        result.passed = False
        result.output = f"Komanda nije pronađena: {cmd[0]}"
        print(result.output, file=sys.stderr)
    except subprocess.TimeoutExpired:
        result.passed = False
        result.output = "Timeout (120s)"
        print(result.output, file=sys.stderr)

    status = "[PASS] PROŠLO" if result.passed else "[FAIL] PALO"
    print(f"  {status} (exit={result.exit_code})")
    return result


def main() -> int:
    """Glavna ulazna tačka. Vraća 0 ako sve prođe, 1 inače."""
    print("FlowOS — verify.py")
    print(f"  Root: {ROOT}")

    steps: list[tuple[str, list[str]]] = [
        ("1. Ruff format check", ["ruff", "format", "--check", "src/", "tests/", "scripts/"]),
        ("2. Ruff lint", ["ruff", "check", "src/", "tests/", "scripts/"]),
        ("3. mypy", [sys.executable, "-m", "mypy", "src", "--explicit-package-bases"]),
        (
            "4. Architecture boundaries",
            ["pytest", "tests/architecture/", "-v", "--tb=short", "--no-header"],
        ),
        (
            "5. Unit tests",
            [
                "pytest",
                "tests/unit/",
                "tests/integration/",
                "tests/contract/",
                "-v",
                "--tb=short",
                "--no-header",
            ],
        ),
    ] + [("6. Migrations check", [sys.executable, "-m", "alembic", "upgrade", "head"])]

    results: list[Result] = []
    for name, cmd in steps:
        result = run_step(name, cmd)
        results.append(result)

    # Sažetak
    print(f"\n{'=' * 60}")
    print("  SAŽETAK")
    print(f"{'=' * 60}")
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    for r in results:
        status = "[PASS]" if r.passed else "[FAIL]"
        print(f"  {status} {r.name}")

    print(f"\n  Prošlo: {passed}/{len(results)}")
    if failed:
        print(f"  Palo:   {failed}/{len(results)}")
        print("\n[FAIL] VERIFIKACIJA NIJE PROŠLA")
        return 1
    else:
        print("\n[PASS] VERIFIKACIJA PROŠLA")
        return 0


if __name__ == "__main__":
    sys.exit(main())
