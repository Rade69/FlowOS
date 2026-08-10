"""Distribucioni bundle — pakuje kod ili exe-ve.

Pokretanje:
  python scripts/package.py           # distribucioni bundle (exe + alembic)
  python scripts/package.py --source  # source bundle (samo kod, bez exe-va)
"""

import shutil
import sys
from pathlib import Path

VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

EXES = ["flowos-service.exe", "flowos-gui.exe", "flowos.exe"]

README_DIST = """============================================================
  FlowOS v{version}
  Lokalni licni operativni sistem
============================================================

POKRETANJE:
  1. flowos-service.exe
  2. flowos-gui.exe --live

VERZIJA: {version}
============================================================
"""

README_SOURCE = """============================================================
  FlowOS v{version} — izvorni kod
  Lokalni licni operativni sistem
============================================================

ZAHTEVI:
  - Python 3.12+
  - pip install -e .  (za development)

POKRETANJE (development):
  Terminal 1:  python src/flowos/service/app.py
  Terminal 2:  python src/flowos/gui/app.py --live

BUILD:
  python scripts/build.py

STRUKTURA:
  src/flowos/       — glavni kod (service, gui, cli, shared)
  scripts/           — build, verify, package, guard_architecture
  tests/             — unit i integracijski testovi
  alembic/           — SQL migracije
  agent_reports/     — agentski izvestaji
  docs/              — planovi, specifikacije
  project_rooms/     — planovi za HIGH/CRITICAL izmene

VERZIJA: {version}
============================================================
"""

# Direktorijumi i fajlovi koji se iskljucuju iz source bundle-a
EXCLUDE_NAMES = {
    "dist",
    "build",
    "__pycache__",
    ".git",
    ".claude",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "review_bundles",
    "artifacts",
    "screenshots",
    "assets",
    "metadata",
    "flowos.db",
    "file",
}
EXCLUDE_SUFFIXES = {".pyc", ".spec", ".egg-info"}


def _should_skip(name: str) -> bool:
    if name in EXCLUDE_NAMES:
        return True
    if name.startswith(".venv"):
        return True
    return name.startswith(".") and name not in (".gitignore", ".gitnexus", ".crush")


def _bundle_dist() -> int:
    """Distribucioni bundle: exe + alembic + ZIP."""
    bundle = DIST / "FlowOS"

    missing = [e for e in EXES if not (DIST / e).exists()]
    if missing:
        print(f"\n[ERROR] Nedostaju exe fajlovi: {missing}")
        print("  Pokreni prvo: python scripts/build.py")
        return 1

    alembic_src = DIST / "alembic"
    if not alembic_src.exists():
        print(f"\n[ERROR] Nedostaje alembic folder u {DIST}")
        print("  Pokreni prvo: python scripts/build.py")
        return 1

    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    print("  Kopiram exe fajlove...")
    for exe in EXES:
        src = DIST / exe
        dst = bundle / exe
        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size / (1024 * 1024)
        print(f"    {exe} ({size_mb:.0f} MB)")

    print("  Kopiram alembic...")
    alembic_dst = bundle / "alembic"
    if alembic_dst.exists():
        shutil.rmtree(alembic_dst)
    shutil.copytree(alembic_src, alembic_dst)

    (bundle / "POKRENI.txt").write_text(README_DIST.format(version=VERSION), encoding="utf-8")

    zip_path = DIST / f"FlowOS-v{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(DIST / f"FlowOS-v{VERSION}"), "zip", str(DIST), "FlowOS")
    zip_size = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n[PASS] Bundle kreiran: {bundle}")
    print(f"  ZIP: {zip_path} ({zip_size:.0f} MB)")
    return 0


def _bundle_source() -> int:
    """Source bundle: ceo kod, bez build/dist/exe artefakata."""
    bundle = DIST / "FlowOS-source"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    print("  Kopiram izvorni kod...")
    total_files = 0
    for item in sorted(ROOT.iterdir()):
        name = item.name
        if _should_skip(name):
            print(f"    [skip]  {name}")
            continue

        dst = bundle / name
        if item.is_dir():
            shutil.copytree(
                item,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", ".DS_Store"),
                dirs_exist_ok=True,
            )
            file_count = sum(1 for _ in dst.rglob("*") if _.is_file())
            print(f"    [dir]   {name}/ ({file_count} fajlova)")
            total_files += file_count
        else:
            shutil.copy2(item, dst)
            print(f"    [file]  {name}")
            total_files += 1

    (bundle / "PROCITAJ.txt").write_text(README_SOURCE.format(version=VERSION), encoding="utf-8")

    zip_path = DIST / f"FlowOS-source-v{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(DIST / f"FlowOS-source-v{VERSION}"), "zip", str(DIST), "FlowOS-source")
    zip_size = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n[PASS] Source bundle kreiran: {bundle}")
    print(f"  Ukupno fajlova: {total_files}")
    print(f"  ZIP: {zip_path} ({zip_size:.0f} MB)")
    return 0


def main() -> int:
    source_mode = "--source" in sys.argv
    mode = "SOURCE (samo kod)" if source_mode else "DIST (exe + alembic)"
    print(f"FlowOS v{VERSION} — pakovanje: {mode}")

    if source_mode:
        return _bundle_source()
    return _bundle_dist()


if __name__ == "__main__":
    sys.exit(main())
