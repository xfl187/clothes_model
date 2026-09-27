"""Versioned structural validation for ComfyUI API-format Workflow manifests."""

from dataclasses import dataclass
from typing import cast

from pydantic import ValidationError

from clothes_model.generated.models import ProviderCapabilities


class WorkflowStructureError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Binding:
    node_id: str
    input_name: str


@dataclass(frozen=True, slots=True)
class OutputBinding:
    node_id: str
    output_index: int


@dataclass(frozen=True, slots=True)
class ParsedManifest:
    schema_version: str
    bindings: dict[str, Binding]
    outputs: tuple[OutputBinding, ...]
    capabilities: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "bindings": sorted(self.bindings),
            "output_count": len(self.outputs),
            "capabilities": self.capabilities,
        }


def parse_manifest(
    manifest: dict[str, object], workflow: dict[str, object]
) -> ParsedManifest:
    if set(manifest) != {"schema_version", "bindings", "outputs", "capabilities"}:
        raise WorkflowStructureError(
            "workflow_manifest_fields_invalid",
            "Manifest 必须且只能包含 schema_version、bindings、outputs、capabilities。",
        )
    schema_version = str(manifest["schema_version"])
    if schema_version != "1":
        raise WorkflowStructureError(
            "workflow_manifest_version_unsupported", "Manifest schema_version 不受支持。"
        )
    raw_bindings = manifest["bindings"]
    if not isinstance(raw_bindings, dict):
        raise WorkflowStructureError("workflow_bindings_invalid", "Manifest bindings 格式无效。")
    binding_map = cast(dict[str, object], raw_bindings)
    required = {"person", "garment", "seed", "candidate_index"}
    allowed = required | {"mask"}
    if not required.issubset(binding_map) or not set(binding_map).issubset(allowed):
        raise WorkflowStructureError(
            "workflow_bindings_incomplete", "Manifest 缺少必需绑定或包含未知绑定。"
        )
    bindings: dict[str, Binding] = {}
    for name, raw in binding_map.items():
        if not isinstance(raw, dict):
            raise WorkflowStructureError(
                "workflow_binding_invalid", f"绑定 {name} 的结构无效。"
            )
        value = cast(dict[str, object], raw)
        if set(value) != {"node_id", "input"}:
            raise WorkflowStructureError(
                "workflow_binding_invalid", f"绑定 {name} 的结构无效。"
            )
        node_id, input_name = value["node_id"], value["input"]
        if (
            not isinstance(node_id, str)
            or not node_id
            or not isinstance(input_name, str)
            or not input_name
        ):
            raise WorkflowStructureError(
                "workflow_binding_invalid", f"绑定 {name} 的节点或输入名无效。"
            )
        node = _workflow_node(workflow, node_id)
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or input_name not in inputs:
            raise WorkflowStructureError(
                "workflow_input_missing", f"绑定 {name} 指向的输入不存在。"
            )
        bindings[name] = Binding(node_id=node_id, input_name=input_name)

    raw_outputs = manifest["outputs"]
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise WorkflowStructureError("workflow_outputs_invalid", "Manifest 必须声明输出。")
    outputs: list[OutputBinding] = []
    for raw in cast(list[object], raw_outputs):
        if not isinstance(raw, dict):
            raise WorkflowStructureError("workflow_output_invalid", "输出绑定结构无效。")
        value = cast(dict[str, object], raw)
        if set(value) != {"node_id", "output_index"}:
            raise WorkflowStructureError("workflow_output_invalid", "输出绑定结构无效。")
        node_id, output_index = value["node_id"], value["output_index"]
        if (
            not isinstance(node_id, str)
            or not node_id
            or not isinstance(output_index, int)
            or isinstance(output_index, bool)
            or output_index < 0
        ):
            raise WorkflowStructureError("workflow_output_invalid", "输出绑定值无效。")
        _workflow_node(workflow, node_id)
        outputs.append(OutputBinding(node_id=node_id, output_index=output_index))

    raw_capabilities = manifest["capabilities"]
    if not isinstance(raw_capabilities, dict):
        raise WorkflowStructureError(
            "workflow_capabilities_invalid", "Manifest capabilities 格式无效。"
        )
    capabilities = cast(dict[str, object], raw_capabilities)
    try:
        ProviderCapabilities.model_validate(capabilities)
    except ValidationError as error:
        raise WorkflowStructureError(
            "workflow_capabilities_invalid", "Manifest capabilities 不符合共享能力契约。"
        ) from error
    manual_mask = cast(dict[str, object], capabilities["manual_mask"])["supported"]
    multiple = cast(dict[str, object], capabilities["multiple_candidates"])["supported"]
    max_candidates = cast(dict[str, object], capabilities["output_constraints"])[
        "max_candidates"
    ]
    if ("mask" in bindings) != bool(manual_mask):
        raise WorkflowStructureError(
            "workflow_capability_contradiction", "mask 绑定与 manual_mask 能力声明冲突。"
        )
    if (int(cast(int, max_candidates)) > 1) != bool(multiple):
        raise WorkflowStructureError(
            "workflow_capability_contradiction",
            "max_candidates 与 multiple_candidates 能力声明冲突。",
        )
    return ParsedManifest(schema_version, bindings, tuple(outputs), capabilities)


def _workflow_node(workflow: dict[str, object], node_id: str) -> dict[str, object]:
    raw = workflow.get(node_id)
    if not isinstance(raw, dict):
        raise WorkflowStructureError("workflow_node_missing", f"Workflow 节点 {node_id} 不存在。")
    node = cast(dict[str, object], raw)
    if not isinstance(node.get("class_type"), str):
        raise WorkflowStructureError(
            "workflow_node_invalid", f"Workflow 节点 {node_id} 缺少 class_type。"
        )
    return node
