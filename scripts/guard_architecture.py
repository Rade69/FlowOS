"""Architecture Guard — brza provera troslojne arhitekture."""
import ast
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Boundary pravila — isto kao u tests/architecture/test_boundaries.py
BOUNDARIES: list[tuple[str, tuple[str, ...]]] = [
    ("flowos.gui.views", ("flowos.gui.services",)),
    (
        "flowos.gui.controllers",
        ("flowos.gui.views", "flowos.service", "sqlalchemy"),
    ),
    (
        "flowos.service.controllers",
        ("flowos.service.services.infrastructure.persistence",),
    ),
    (
        "flowos.service.services",
        ("flowos.gui", "flowos.service.controllers"),
    ),
    ("flowos.shared", ("flowos.gui", "flowos.service", "flowos.cli")),
]


def _get_imports(file_path: Path) -> list[str]:
    """Izvlači sve import putanje iz Python fajla."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _matches_boundary(module: str, boundary: str) -> bool:
    """Proverava da li modul pripada boundary-ju (prefiksno)."""
    return module == boundary or module.startswith(boundary + ".")


def _find_source_module(file_path: Path) -> str | None:
    """Konvertuje putanju fajla u Python modul (npr. flowos.service.controllers...)."""
    try:
        rel = file_path.resolve().relative_to(SRC.resolve())
    except ValueError:
        return None
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def main() -> int:
    violations: list[str] = []

    for py_file in SRC.rglob("*.py"):
        source_module = _find_source_module(py_file)
        if not source_module:
            continue

        imports = _get_imports(py_file)

        for boundary_source, forbidden_prefixes in BOUNDARIES:
            if not _matches_boundary(source_module, boundary_source):
                continue

            for imp in imports:
                for forbidden in forbidden_prefixes:
                    if _matches_boundary(imp, forbidden):
                        violations.append(
                            f"  {py_file.relative_to(ROOT)}: "
                            f"zabranjen import '{imp}' → pripada '{forbidden}'"
                        )

    if violations:
        print(f"[FAIL] {len(violations)} arhitektonskih prekršaja:")
        for v in violations:
            print(v)
        return 1

    print("[PASS] Arhitektura cista — nema zabranjenih importa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
