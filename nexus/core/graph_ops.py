from typing import List
from nexus.core.schemas import (
    LogicalGraph,
    Operation,
    NodeInstance,
    EdgeInstance,
    OpType,
    ApplyResult,
    OperationError,
)
import uuid
from nexus.config.logger import get_logger

logger = get_logger(__name__)

def apply_operations(graph: LogicalGraph, operations: List[Operation]) -> ApplyResult:
    """将操作应用到当前图上，生成新图和摘要。

    设计目标：
    - 保证原子操作可回放（Operation -> Graph 的确定性转换）。
    - 在不中断流程的情况下收集错误（错误码 + 说明）。
    - 返回应用结果统计，供 UI/审查使用。
    """
    # 深拷贝或新建
    # 以 ID 索引现有节点，便于增删改查
    nodes = {n.id: n for n in graph.nodes}
    # 以四元组索引边，保证 source/target/handle 唯一性
    edges = {(e.source, e.target, e.source_handle, e.target_handle): e for e in graph.edges}
    
    # 收集错误而不是抛异常，避免阻塞流式 UI 更新
    errors: List[OperationError] = []
    # 统计真正应用成功的操作数
    applied_ops = 0

    for op in operations:
        if op.op_type == OpType.ADD_NODE:
            node_id = op.params.get("id") or op.target_id or str(uuid.uuid4())[:8]
            node_type = op.params.get("type")
            if not node_type:
                errors.append(OperationError(
                    code="MISSING_NODE_TYPE",
                    message="ADD_NODE missing type",
                    op_id=op.op_id,
                    target_id=node_id,
                ))
                continue
            # 新增节点：把节点完整结构收敛进 data，顶层仅保留 id/type
            base_data = op.params.get("data") or {}
            if not base_data:
                base_data = {
                    "flowNodeType": node_type,
                    "name": op.params.get("name") or op.params.get("label"),
                    "icon": op.params.get("icon"),
                    "avatar": op.params.get("avatar"),
                    "version": op.params.get("version"),
                    "intro": op.params.get("intro"),
                    "position": op.params.get("position"),
                    "inputs": op.params.get("inputs", []),
                    "outputs": op.params.get("outputs", []),
                    "nodeId": node_id,
                }
            nodes[node_id] = NodeInstance(
                id=node_id,
                type=node_type,
                data=base_data,
            )
            applied_ops += 1

        elif op.op_type == OpType.REMOVE_NODE:
            target_id = op.target_id or op.params.get("id")
            if target_id in nodes:
                del nodes[target_id]
                edges = {k: v for k, v in edges.items() if k[0] != target_id and k[1] != target_id}
                applied_ops += 1
            else:
                errors.append(OperationError(
                    code="NODE_NOT_FOUND",
                    message=f"Node not found: {target_id}",
                    op_id=op.op_id,
                    target_id=target_id,
                ))

        elif op.op_type == OpType.ADD_EDGE:
            source = op.params.get("source")
            target = op.params.get("target")
            if source and target:
                source_handle = op.params.get("source_handle")
                target_handle = op.params.get("target_handle")
                edges[(source, target, source_handle, target_handle)] = EdgeInstance(
                    source=source,
                    target=target,
                    source_handle=source_handle,
                    target_handle=target_handle
                )
                applied_ops += 1

        elif op.op_type == OpType.REMOVE_EDGE:
            source = op.params.get("source")
            target = op.params.get("target")
            source_handle = op.params.get("source_handle")
            target_handle = op.params.get("target_handle")
            if source and target:
                removed = edges.pop((source, target, source_handle, target_handle), None)
                if removed:
                    applied_ops += 1
                else:
                    errors.append(OperationError(
                        code="EDGE_NOT_FOUND",
                        message=f"Edge not found: {source} -> {target}",
                        op_id=op.op_id,
                    ))

        elif op.op_type == OpType.UPDATE_INPUTS:
            if op.target_id in nodes:
                node = nodes[op.target_id]
                updates = op.params.get("inputs") or []
                if not updates:
                    errors.append(OperationError(
                        code="INVALID_OP",
                        message="UPDATE_INPUTS requires inputs",
                        op_id=op.op_id,
                        target_id=op.target_id,
                    ))
                    continue

                data_inputs = []
                if isinstance(node.data, dict):
                    raw_inputs = node.data.get("inputs")
                    if isinstance(raw_inputs, list):
                        data_inputs = raw_inputs

                input_map = {
                    item.get("key"): item
                    for item in data_inputs
                    if isinstance(item, dict) and item.get("key")
                }
                missing_keys = [
                    update.get("key")
                    for update in updates
                    if update.get("key") not in input_map
                ]
                if missing_keys:
                    for key in missing_keys:
                        errors.append(OperationError(
                            code="INVALID_OP",
                            message=f"Input key not found: {key}",
                            op_id=op.op_id,
                            target_id=op.target_id,
                        ))
                    continue

                for update in updates:
                    key = update.get("key")
                    if key in input_map:
                        input_map[key]["value"] = update.get("value")
                node.data["inputs"] = data_inputs
                applied_ops += 1
            else:
                errors.append(OperationError(
                    code="NODE_NOT_FOUND",
                    message=f"Node not found: {op.target_id}",
                    op_id=op.op_id,
                    target_id=op.target_id,
                ))

        elif op.op_type == OpType.AUTO_HEAL:
            # AUTO_HEAL 暂不实现具体策略，保留扩展点
            continue

    # 汇总结果（图 + 错误 + 计数）
    return ApplyResult(
        graph=LogicalGraph(
            nodes=list(nodes.values()),
            edges=list(edges.values())
        ),
        errors=errors,
        applied_ops=applied_ops,
    )
