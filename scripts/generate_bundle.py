"""Review bundle generator — pravi potpun review paket za nezavisni pregled.

Pokretanje: python scripts/generate_bundle.py <bundle_name>

Generiše:
- git_status.txt, git_log.txt
- test_results.txt, lint_results.txt, mypy_results.txt
- architecture_check.txt, migration_results.txt, verify_results.txt
- changes.diff (pun diff)
- source/ (svi izmenjeni fajlovi)
- metadata/ (environment.txt)
- bundle_manifest.txt (SHA-256 heševi)
- README_REVIEW.md (šablon)
"""

import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
BUNDLES_DIR = ROOT / "review_bundles"


def run(cmd: list[str], output_file: Path) -> bool:
    """Pokreće komandu i čuva izlaz u fajl."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        output_file.write_text(output, encoding="utf-8")
        return result.returncode == 0
    except Exception as e:
        output_file.write_text(f"Error: {e}", encoding="utf-8")
        return False


def generate(bundle_name: str) -> int:
    """Generiše review bundle."""
    bundle_dir = BUNDLES_DIR / bundle_name

    if bundle_dir.exists():
        print(f"Bundle direktorijum već postoji: {bundle_dir}")
        return 1

    bundle_dir.mkdir(parents=True)
    meta_dir = bundle_dir / "metadata"
    meta_dir.mkdir()
    source_dir = bundle_dir / "source"
    source_dir.mkdir()

    print(f"Generating bundle: {bundle_name}")
    print(f"  Directory: {bundle_dir}")

    # 1. Git status i log
    print("  [1/10] Git status & log...")
    subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(ROOT),
        stdout=(bundle_dir / "git_status.txt").open("w"),
        stderr=subprocess.STDOUT,
    )
    subprocess.run(
        ["git", "log", "--oneline", "-30"],
        cwd=str(ROOT),
        stdout=(bundle_dir / "git_log.txt").open("w"),
        stderr=subprocess.STDOUT,
    )

    # 2. Diff
    print("  [2/10] Changes diff...")
    subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=str(ROOT),
        stdout=(bundle_dir / "changes.diff").open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    # 3. Ruff lint
    print("  [3/10] Ruff lint...")
    run(["ruff", "check", "src/", "tests/", "scripts/"], bundle_dir / "lint_results.txt")

    # 4. mypy
    print("  [4/10] mypy...")
    run(
        [
            sys.executable,
            "-m",
            "mypy",
            "src/flowos/service",
            "src/flowos/shared",
            "src/flowos/cli",
            "--ignore-missing-imports",
        ],
        bundle_dir / "mypy_results.txt",
    )

    # 5. Architecture
    print("  [5/10] Architecture tests...")
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/architecture/",
            "-v",
            "--tb=short",
            "--no-header",
        ],
        bundle_dir / "architecture_check.txt",
    )

    # 6. Unit tests
    print("  [6/10] Unit tests...")
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--tb=short",
        ],
        bundle_dir / "test_results.txt",
    )

    # 7. Migracije
    print("  [7/10] Migrations...")
    run(
        [sys.executable, "-m", "alembic", "history"],
        bundle_dir / "migration_results.txt",
    )

    # 8. verify.py
    print("  [8/10] verify.py...")
    run(
        [sys.executable, str(ROOT / "scripts" / "verify.py")],
        bundle_dir / "verify_results.txt",
    )

    # 9. Source fajlovi
    print("  [9/10] Copying source files...")
    changed = (
        subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .split("\n")
    )

    new_files = (
        subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .split("\n")
    )

    EXCLUDE_PREFIXES = ("review_bundles/", "metadata/", ".git/")

    count = 0
    for f in changed + new_files:
        if not f or not f.endswith(".py"):
            continue
        if f.startswith(EXCLUDE_PREFIXES):
            continue
        src = ROOT / f
        if src.is_file():
            dst = source_dir / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            count += 1

    print(f"    {count} source files copied")

    # 10. Metadata
    print("  [10/10] Metadata & manifest...")
    env_file = meta_dir / "environment.txt"
    env_file.write_text(
        f"python_version: {sys.version}\n"
        f"python_path: {sys.executable}\n"
        f"platform: {sys.platform}\n"
        f"generated_at: {datetime.now(tz=UTC).isoformat()}\n"
    )

    # Bundle manifest sa SHA-256
    manifest_lines = []
    for root_dir, _dirs, files in os.walk(bundle_dir):
        for f in sorted(files):
            path = Path(root_dir) / f
            rel = path.relative_to(bundle_dir)
            size = path.stat().st_size
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_lines.append(f"{rel} | {size} bytes | {sha}")

    (bundle_dir / "bundle_manifest.txt").write_text("\n".join(manifest_lines), encoding="utf-8")

    # ZIP
    zip_path = BUNDLES_DIR / f"{bundle_name}.zip"
    print(f"  Creating ZIP: {zip_path}")
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for root_dir, _dirs, files in os.walk(bundle_dir):
            for f in files:
                path = Path(root_dir) / f
                arcname = str(path.relative_to(bundle_dir))
                zf.write(path, arcname)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\nBundle ready: {zip_path} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_bundle.py <bundle_name>")
        print("Example: python scripts/generate_bundle.py FLOW-CORRECTION-A")
        sys.exit(1)

    sys.exit(generate(sys.argv[1]))
