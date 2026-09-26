import re
from pathlib import Path

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings


def test_every_contract_operation_has_a_registered_route() -> None:
    repository_root = Path(__file__).parents[2]
    paths_root = repository_root / "contracts" / "openapi" / "paths"
    contract_operation_ids = {
        match.group(1)
        for path in paths_root.glob("*.yaml")
        for match in re.finditer(r"^\s*operationId:\s*(\S+)\s*$", path.read_text(), re.MULTILINE)
    }
    app = create_app(Settings(environment="test"))
    backend_openapi = app.openapi()
    registered_operation_ids = {
        operation["operationId"]
        for path_item in backend_openapi["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    }

    assert registered_operation_ids == contract_operation_ids
