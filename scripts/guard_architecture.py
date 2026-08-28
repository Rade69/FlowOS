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
    ("flowos.gui.views", ("flowos.gui.services", "subprocess", "os")),
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
    (
        "flowos.cli",
        (
            "flowos.service.services.infrastructure.persistence",
            "sqlalchemy",
            "PySide6",
        ),
    ),
]

# flowos.gui.composition_root: privatne metode/atributi GuiApiClient-a koje
# pozivalac van klijenta samog nikad ne smije dirati direktno — FLOW-1156.
COMPOSITION_ROOT_MODULE = "flowos.gui.composition_root"
FORBIDDEN_PRIVATE_API_ATTRS = frozenset({"_post", "_get", "_nam", "_apply_auth_header"})

# ensure_service_running() legitimno pokreće FlowOS-ov sopstveni backend
# (flowos.service.app) kao subprocess — to je infra bootstrap, ne OS-shell
# "otvori folder" akcija koju FLOW-1157 izbacio iz composition_root-a u
# SystemController. Vidi agent_reports/2026-08-28-FLOW-1156-*.md.
COMPOSITION_ROOT_SUBPROCESS_EXEMPT_FUNCTIONS = frozenset({"ensure_service_running"})


class _CompositionRootVisitor(ast.NodeVisitor):
    """AST provjera poziva koje import-based BOUNDARIES ne vidi.

    Import-based provjera hvata samo `import X` / `from X import Y`. Ovdje
    treba uhvatiti (1) pristup privatnim atributima API klijenta bilo gdje
    u fajlu, i (2) subprocess/os.system, osim unutar eksplicitno izuzete
    funkcije koja pokreće sopstveni FlowOS servis.
    """

    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []
        self._func_stack: list[str] = []

    def _in_exempt_function(self) -> bool:
        return bool(self._func_stack) and (
            self._func_stack[-1] in COMPOSITION_ROOT_SUBPROCESS_EXEMPT_FUNCTIONS
        )

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_PRIVATE_API_ATTRS:
            self.violations.append(
                (
                    node.lineno,
                    f"direktan pristup privatnom '{node.attr}' GuiApiClient-a "
                    "(koristi javnu metodu klijenta)",
                )
            )
        if (
            node.attr == "system"
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and not self._in_exempt_function()
        ):
            self.violations.append((node.lineno, "os.system poziv nije dozvoljen"))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        if not self._in_exempt_function():
            for alias in node.names:
                if alias.name == "subprocess":
                    self.violations.append(
                        (node.lineno, "subprocess import nije dozvoljen u composition_root")
                    )
        self.generic_visit(node)


def _check_composition_root(file_path: Path, source_module: str) -> list[str]:
    if source_module != COMPOSITION_ROOT_MODULE:
        return []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    visitor = _CompositionRootVisitor()
    visitor.visit(tree)
    return [
        f"  {file_path.relative_to(ROOT)}:{lineno}: {message}"
        for lineno, message in sorted(visitor.violations)
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
        elif isinstance(node, ast.ImportFrom) and node.module:
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

        violations.extend(_check_composition_root(py_file, source_module))

    if violations:
        print(f"[FAIL] {len(violations)} arhitektonskih prekršaja:")
        for v in violations:
            print(v)
        return 1

    print("[PASS] Arhitektura cista — nema zabranjenih importa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
