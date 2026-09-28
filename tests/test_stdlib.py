"""Reject third-party imports throughout runtime sources."""

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_imports_are_stdlib_only():
    allowed = sys.stdlib_module_names | {"wuwei"}
    sources = sorted((ROOT / "cli").rglob("*.py"))
    assert sources, "the CLI package must exist"
    sources += sorted((ROOT / "adapters").rglob("*.py"))
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text(), filename=str(source))):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [node.module.split(".")[0]]
            else:
                continue
            assert set(names) <= allowed, (source, node.lineno, names)
