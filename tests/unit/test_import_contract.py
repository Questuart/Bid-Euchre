"""Test architectural import contracts between reporting and diagnostics."""
import ast
from pathlib import Path

SRC = Path(__file__).parent.parent.parent / "src" / "bid_euchre"


def _get_imports(filepath: Path) -> set[str]:
    """Extract all import module paths from a Python file."""
    tree = ast.parse(filepath.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_diagnostics_only_imports_reporting_style():
    """diagnostics/ may only depend on reporting.style, not broader reporting."""
    diag_dir = SRC / "diagnostics"
    for py_file in diag_dir.glob("*.py"):
        imports = _get_imports(py_file)
        for imp in imports:
            if "reporting" in imp:
                assert imp.endswith(".style") or imp.endswith("reporting.style"), (
                    f"{py_file.name} imports {imp} — diagnostics may only import reporting.style"
                )


def test_reporting_init_does_not_import_charts():
    """reporting/__init__.py must not import reporting.charts (circular import risk)."""
    init_file = SRC / "reporting" / "__init__.py"
    imports = _get_imports(init_file)
    for imp in imports:
        assert "charts" not in imp, (
            f"reporting/__init__.py imports {imp} — this would cause circular import"
        )


def test_reporting_style_has_no_back_imports():
    """reporting/style.py must not import from diagnostics."""
    style_file = SRC / "reporting" / "style.py"
    imports = _get_imports(style_file)
    for imp in imports:
        assert "diagnostics" not in imp, (
            f"reporting/style.py imports {imp} — back-edge to diagnostics forbidden"
        )
