import networkx as nx
from typing import Dict
from nexus.core.schemas import LogicalGraph
from nexus.config.logger import get_logger

logger = get_logger(__name__)

class Layouter:
    """
    负责计算图的布局（坐标）。
    将逻辑图 (LogicalGraph) 转换为带有位置信息的视图数据。
    """
    
    def __init__(self, rank_sep: int = 250, node_sep: int = 150):
        self.rank_sep = rank_sep  # 层级间距 (X轴)
        self.node_sep = node_sep  # 节点间距 (Y轴)

    def layout(self, graph: LogicalGraph) -> Dict[str, Dict[str, int]]:
        """
        计算每个节点的 (x, y) 坐标。
        返回格式: { "node_id": {"x": 100, "y": 200} }
        """
        if not graph.nodes:
            return {}

        # 1. 构建 NetworkX 图
        G = nx.DiGraph()
        for node in graph.nodes:
            G.add_node(node.id)
        
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)

        # 2. 检查是否有环，如果有则打破（简单处理，Layout需要DAG）
        if not nx.is_directed_acyclic_graph(G):
            # 这里的处理比较粗暴，实际可能需要反馈给 Agent
            # 暂时忽略环，尝试布局
            pass

        # 3. 计算层级布局 (简单的分层算法)
        # 使用 networkx 的 multipartite_layout 或自定义分层
        # 这里实现一个简单的基于拓扑分代的布局
        
        pos = {}
        try:
            # 获取拓扑分代
            generations = list[list](nx.topological_generations(G))
            
            for gen_index, gen_nodes in enumerate[list](generations):
                x = gen_index * self.rank_sep
                
                # 计算该层的 Y 轴起始点，使其居中
                layer_height = (len(gen_nodes) - 1) * self.node_sep
                start_y = -layer_height / 2
                
                for node_index, node_id in enumerate(sorted(gen_nodes)): # sort 保证确定性
                    y = start_y + node_index * self.node_sep
                    pos[node_id] = {"x": int(x), "y": int(y)}
                    
        except Exception:
            # 如果拓扑排序失败（有环），回退到 spring_layout
            raw_pos = nx.spring_layout(G, k=self.rank_sep, seed=42)
            for node_id, coords in raw_pos.items():
                # spring_layout 返回归一化坐标，需要缩放
                pos[node_id] = {"x": int(coords[0] * 1000), "y": int(coords[1] * 1000)}

        return pos
