from typing import List
from core.schemas import LogicalGraph, Operation, NodeInstance, EdgeInstance, OpType
import uuid
from config.logger import get_logger

logger = get_logger(__name__)

def apply_operations(graph: LogicalGraph, operations: List[Operation]) -> LogicalGraph:
    """
    将操作应用到当前图上，生成新图。
    这里是一个简化的内存实现。
    """
    # 深拷贝或新建
    nodes = {n.id: n for n in graph.nodes}
    edges = {(e.source, e.target): e for e in graph.edges}
    
    for op in operations:
        if op.op_type == "ADD_NODE":
            # 必须提供 ID，如果没有则生成
            node_id = op.params.get("id") or op.target_id or str(uuid.uuid4())[:8]
            node_type = op.params.get("type")
            config = op.params.get("config", {})
            
            if not node_type:
                continue # Skip invalid
                
            nodes[node_id] = NodeInstance(
                id=node_id,
                type=node_type,
                config=config,
                label=op.params.get("label")
            )
            
        elif op.op_type == "REMOVE_NODE":
            if op.target_id in nodes:
                del nodes[op.target_id]
                # 同时也需要删除相关连线
                edges = {k: v for k, v in edges.items() if k[0] != op.target_id and k[1] != op.target_id}
                
        elif op.op_type == "ADD_EDGE":
            source = op.params.get("source")
            target = op.params.get("target")
            if source and target:
                edges[(source, target)] = EdgeInstance(
                    source=source,
                    target=target,
                    source_handle=op.params.get("source_handle"),
                    target_handle=op.params.get("target_handle")
                )
        
        elif op.op_type == "UPDATE_CONFIG":
            if op.target_id in nodes:
                node = nodes[op.target_id]
                new_config = op.params.get("config", {})
                node.config.update(new_config)
                
        # ... 处理其他操作类型
        
    return LogicalGraph(
        nodes=list(nodes.values()),
        edges=list(edges.values())
    )
