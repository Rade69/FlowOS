"""Testovi arhitektonskih granica.

Sprovođenje pravila iz §4.4 i §4.5 plana:
- View ne sme importovati Services direktno
- Controller ne sme importovati SQLite/Git/subprocess
- Services ne sme importovati PySide6
- Shared ne sme importovati gui/service/cli

Svaki test proverava da zabranjeni import baca ImportError ili
da modul ne sadrži zabranjene import statemente u svom AST-u.
"""

import ast
import importlib
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent / "src"

# Granice iz §4.5 — svaka je (izvorni_modul, zabranjeni_import_prefixi)
BOUNDARIES: list[tuple[str, tuple[str, ...]]] = [
    ("flowos.shared", ("flowos.gui", "flowos.service", "flowos.cli")),
    ("flowos.gui.views", ("flowos.gui.services", "subprocess", "os")),
    ("flowos.gui.controllers", ("flowos.service.services",)),
    ("flowos.service.services", ("flowos.gui", "PySide6", "flowos.cli")),
    ("flowos.service.controllers", ("flowos.service.services.infrastructure.persistence",)),
    (
        "flowos.cli",
        ("flowos.service.services.infrastructure.persistence", "sqlalchemy", "PySide6"),
    ),
]


def _get_module_imports(module_path: Path) -> set[str]:
    """Ekstrahuje sve import nazive iz Python modula koristeći AST."""
    imports: set[str] = set()
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _collect_module_paths(package: str) -> list[Path]:
    """Skuplja sve .py fajlove u datom paketu."""
    rel = package.replace(".", "/")
    pkg_path = SRC / rel
    if not pkg_path.exists():
        return []
    if pkg_path.is_file():
        return [pkg_path]
    return list(pkg_path.rglob("*.py"))


@pytest.mark.parametrize("source,forbidden", BOUNDARIES)
def test_boundary_no_forbidden_imports(source: str, forbidden: tuple[str, ...]) -> None:
    """Proverava da source modul ne uvozi nijedan zabranjen modul."""
    violations: list[str] = []

    for module_path in _collect_module_paths(source):
        imports = _get_module_imports(module_path)
        for imp in imports:
            for fb in forbidden:
                if imp == fb or imp.startswith(fb + "."):
                    violations.append(
                        f"{module_path.relative_to(SRC.parent)}: "
                        f"zabranjen import '{imp}' (iz '{fb}')"
                    )

    # Guard: test mora pasti ako nije pronasao nijedan modul
    paths = _collect_module_paths(source)
    assert paths, f"Nijedan modul nije pronadjen za '{source}' — proveri SRC putanju"

    assert not violations, (
        f"\nArhitektonske granice narušene u '{source}':\n"
        + "\n".join(f"  • {v}" for v in violations)
        + "\n\nDozvoljene zavisnosti su definisane u §4.4 plana."
    )


def test_package_imports_are_clean() -> None:
    """Proverava da svi flowos paketi mogu da se uvezu bez grešaka."""
    packages = [
        "flowos.shared",
        "flowos.shared.contracts",
        "flowos.shared.enums",
        "flowos.shared.errors",
        "flowos.shared.time",
        "flowos.gui",
        "flowos.gui.services",
        "flowos.service",
        "flowos.service.controllers",
        "flowos.cli",
        "flowos.cli.services",
    ]
    errors: list[str] = []
    for pkg in packages:
        try:
            importlib.import_module(pkg)
        except ImportError as e:
            errors.append(f"  • {pkg}: {e}")

    assert not errors, "Neki paketi ne mogu da se uvezu:\n" + "\n".join(errors)


def test_shared_does_not_depend_on_other_layers() -> None:
    """Shared ne sme uvoziti gui, service ili cli."""
    forbidden = ("flowos.gui", "flowos.service", "flowos.cli")
    violations: list[str] = []

    for module_path in _collect_module_paths("flowos.shared"):
        imports = _get_module_imports(module_path)
        for imp in imports:
            for fb in forbidden:
                if imp == fb or imp.startswith(fb + "."):
                    violations.append(f"{module_path.name}: {imp}")

    assert not violations, "flowos.shared nesme zavisiti od gui/service/cli:\n" + "\n".join(
        f"  • {v}" for v in violations
    )


# ── composition_root call-level granice (FLOW-1156) ──────────────────
#
# Import-based provjera iznad hvata samo `import X`/`from X import Y`.
# composition_root.py je god-fajl rizik: privatna metoda API klijenta
# (self._api._post(...)) se poziva kroz javni GuiApiClient objekat, ne
# kroz zaseban import, pa mora AST provjera poziva/atributa, ne importa.
# Ogledalo scripts/guard_architecture.py _CompositionRootVisitor — vidi
# agent_reports/2026-08-28-FLOW-1156-*.md za dokaz replaya na b83f197.

FORBIDDEN_PRIVATE_API_ATTRS = frozenset({"_post", "_get", "_nam", "_apply_auth_header"})
COMPOSITION_ROOT_SUBPROCESS_EXEMPT_FUNCTIONS = frozenset({"ensure_service_running"})


class _CompositionRootCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []
        self._func_stack: list[str] = []

    def _in_exempt_function(self) -> bool:
        return bool(self._func_stack) and (
            self._func_stack[-1] in COMPOSITION_ROOT_SUBPROCESS_EXEMPT_FUNCTIONS
        )

    def _visit_function(self, node) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_PRIVATE_API_ATTRS:
            self.violations.append((node.lineno, f"privatan '{node.attr}' pozvan direktno"))
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
                    self.violations.append((node.lineno, "subprocess import nije dozvoljen"))
        self.generic_visit(node)


def _composition_root_path() -> Path:
    return SRC / "flowos" / "gui" / "composition_root.py"


def test_composition_root_does_not_call_private_api_client_methods() -> None:
    """composition_root.py ne smije direktno zvati _post/_get/_nam/_apply_auth_header."""
    path = _composition_root_path()
    assert path.exists(), f"composition_root.py nije nadjen na {path}"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    visitor = _CompositionRootCallVisitor()
    visitor.visit(tree)

    private_attr_hits = [(line, msg) for line, msg in visitor.violations if "privatan" in msg]
    assert not private_attr_hits, (
        "composition_root.py zove privatne metode GuiApiClient-a direktno:\n"
        + "\n".join(f"  • linija {line}: {msg}" for line, msg in private_attr_hits)
    )


def test_composition_root_does_not_shell_out_except_service_bootstrap() -> None:
    """composition_root.py ne smije subprocess/os.system osim u ensure_service_running."""
    path = _composition_root_path()
    assert path.exists(), f"composition_root.py nije nadjen na {path}"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    visitor = _CompositionRootCallVisitor()
    visitor.visit(tree)

    shell_hits = [
        (line, msg) for line, msg in visitor.violations if "subprocess" in msg or "os.system" in msg
    ]
    assert not shell_hits, (
        "composition_root.py pokrece OS proces van ensure_service_running:\n"
        + "\n".join(f"  • linija {line}: {msg}" for line, msg in shell_hits)
    )
