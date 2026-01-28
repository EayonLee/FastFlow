from typing import List

from nexus.core.schemas import LogicalGraph


def validate_graph(graph: LogicalGraph) -> List[str]:
    """最小化校验：确保结构完整与引用有效。

    校验维度：
    - 节点/边完整性（缺失 ID、类型、输入输出）。
    - 引用有效性（边引用节点必须存在）。
    - 业务硬规则（userGuide/workflowStart 必须存在）。
    - 基本拓扑检查（终端节点、不可达节点）。
    """
    errors: List[str] = []

    # 节点 ID 必须唯一
    node_ids = [node.id for node in graph.nodes]
    duplicates = {node_id for node_id in node_ids if node_ids.count(node_id) > 1}
    if duplicates:
        errors.append(f"Duplicate node ids: {sorted(duplicates)}")

    node_set = set(node_ids)
    # 节点结构完整性检查
    for node in graph.nodes:
        if not node.id or not node.type:
            errors.append("Node missing id or type")
        cfg = node.data if isinstance(node.data, dict) else {}
        inputs = cfg.get("inputs")
        outputs = cfg.get("outputs")
        if not isinstance(inputs, list) or not isinstance(outputs, list):
            errors.append(f"Node {node.id} missing inputs or outputs")

    # 边引用必须有效
    for edge in graph.edges:
        if edge.source not in node_set or edge.target not in node_set:
            errors.append(f"Edge invalid: {edge.source} -> {edge.target}")

    # 业务硬规则：必须存在基础系统节点
    types = [node.type for node in graph.nodes]
    if "userGuide" not in types:
        errors.append("Missing required node: userGuide")
    if "workflowStart" not in types:
        errors.append("Missing required node: workflowStart")

    # 拓扑检查：至少存在终点
    if graph.nodes:
        target_ids = {edge.target for edge in graph.edges}
        terminal_nodes = [node.id for node in graph.nodes if node.id not in target_ids]
        if not terminal_nodes:
            errors.append("No terminal nodes found")

    # 从系统节点出发，检测不可达节点
    unreachable = set(node_ids)
    start_nodes = [node.id for node in graph.nodes if node.type in ("userGuide", "workflowStart")]
    frontier = list(start_nodes)
    visited = set()
    edges_by_source = {}
    for edge in graph.edges:
        edges_by_source.setdefault(edge.source, []).append(edge.target)
    while frontier:
        node_id = frontier.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        for target_id in edges_by_source.get(node_id, []):
            if target_id not in visited:
                frontier.append(target_id)
    unreachable -= visited
    if unreachable:
        errors.append(f"Unreachable nodes: {sorted(unreachable)}")

    return errors
