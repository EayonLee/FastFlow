import json
from json import JSONDecodeError
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator
from pydantic.config import ConfigDict


class NodeInstance(BaseModel):
    """
    前端导出中的节点对象。
    """
    # Pydantic v2 模型级配置，不是业务字段，extra="allow" 表示允许并保留未在类中显式声明的扩展字段。model_config 由 Pydantic 约定，不能随意改名
    model_config = ConfigDict(extra="allow")

    node_id: str = Field(..., description="唯一的节点 ID", alias="nodeId")
    flow_node_type: str = Field(..., description="节点类型", alias="flowNodeType")


class EdgeInstance(BaseModel):
    """
    前端导出中的边对象。
    """
    # Pydantic v2 模型级配置，不是业务字段，extra="allow" 表示允许并保留未在类中显式声明的扩展字段。model_config 由 Pydantic 约定，不能随意改名
    model_config = ConfigDict(extra="allow")

    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    source_handle: Optional[str] = Field(None, alias="sourceHandle")
    target_handle: Optional[str] = Field(None, alias="targetHandle")


class WorkflowGraph(BaseModel):
    """
    工作流图（与前端导出结构对齐）：nodes / edges / chatConfig。
    """
    # Pydantic v2 模型级配置，不是业务字段，extra="allow" 表示允许并保留未在类中显式声明的扩展字段。model_config 由 Pydantic 约定，不能随意改名
    model_config = ConfigDict(extra="allow")

    nodes: List[NodeInstance] = Field(default_factory=list)
    edges: List[EdgeInstance] = Field(default_factory=list)
    chat_config: Dict[str, Any] = Field(default_factory=dict, alias="chatConfig")

    @model_validator(mode="before")
    @classmethod
    def parse_raw_export(cls, value: Any) -> Any:
        """
        允许 workflow_graph 直接接收前端导出的 JSON 字符串。
        """
        if value is None:
            return None

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {"nodes": [], "edges": [], "chatConfig": {}}
            try:
                parsed = json.loads(text)
            except JSONDecodeError as exc:
                raise ValueError("workflow_graph is not valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("workflow_graph JSON must be an object")
            return parsed

        if hasattr(value, "model_dump"):
            return value.model_dump(by_alias=True)

        return value
