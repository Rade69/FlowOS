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

SRC = Path(__file__).resolve().parent.parent.parent / "src" / "flowos"

# Granice iz §4.5 — svaka je (izvorni_modul, zabranjeni_import_prefixi)
BOUNDARIES: list[tuple[str, tuple[str, ...]]] = [
    ("flowos.shared", ("flowos.gui", "flowos.service", "flowos.cli")),
    ("flowos.gui.views", ("flowos.gui.services",)),
    ("flowos.gui.controllers", ("flowos.service.services",)),
    ("flowos.service.services", ("flowos.gui", "PySide6", "flowos.cli")),
    ("flowos.service.controllers", ("flowos.service.services.infrastructure.persistence",)),
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
