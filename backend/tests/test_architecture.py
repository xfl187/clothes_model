import ast
from pathlib import Path


def test_domain_and_application_layers_do_not_import_frameworks() -> None:
    source_root = Path(__file__).parents[1] / "src" / "clothes_model"
    forbidden_roots = {"fastapi", "sqlalchemy", "aiosqlite", "sqlite3"}
    violations: list[str] = []

    for path in source_root.rglob("*.py"):
        if not ({"domain", "application"} & set(path.parts)):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = {node.module.split(".")[0]}
            else:
                continue
            if imported & forbidden_roots:
                violations.append(f"{path}: {sorted(imported & forbidden_roots)}")

    assert violations == []
