from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class NodeInstance(BaseModel):
    """
    图中节点的具体实例。
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="唯一的实例 ID", alias="nodeId")
    type: str = Field(..., description="节点类型", alias="flowNodeType")
    data: Dict[str, Any] = Field(default_factory=dict, description="节点完整结构")


class EdgeInstance(BaseModel):
    """
    两个节点之间的连接。
    """

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    source_handle: Optional[str] = Field(None, alias="sourceHandle")
    target_handle: Optional[str] = Field(None, alias="targetHandle")


class WorkflowGraph(BaseModel):
    """
    工作流图的逻辑表示（仅拓扑结构）。
    """

    nodes: List[NodeInstance] = Field(default_factory=list)
    edges: List[EdgeInstance] = Field(default_factory=list)
