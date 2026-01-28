from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


# --- Graph Structures ---

class NodeDefinition(BaseModel):
    """
    注册表中可用的节点类型定义。
    """
    type: str = Field(..., description="唯一的类型标识符，例如 'workflow-start'")
    label: str = Field(..., description="显示名称，例如 '开始节点'")
    category: str = Field(..., description="分组类别")
    input_type: Optional[str] = Field(None, description="输入期望的数据类型")
    output_type: Optional[str] = Field(None, description="输出产生的数据类型")
    config_schema: Dict[str, Any] = Field(default_factory=dict, alias="schema",
                                          description="用于配置参数的 JSON Schema")


class NodeInstance(BaseModel):
    """
    图中节点的具体实例。
    """
    id: str = Field(..., description="唯一的实例 ID")
    type: str = Field(..., description="必须匹配 NodeDefinition.type")
    label: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict, description="配置值")
    # 注意：这里不包含位置信息，位置由 Layouter 处理


class EdgeInstance(BaseModel):
    """
    两个节点之间的连接。
    """
    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


class LogicalGraph(BaseModel):
    """
    工作流图的逻辑表示（仅拓扑结构）。
    不包含 UI 布局信息。
    """
    nodes: List[NodeInstance] = Field(default_factory=list)
    edges: List[EdgeInstance] = Field(default_factory=list)


# --- Agent 协议 ---

class OpType(str, Enum):
    ADD_NODE = "ADD_NODE"
    REMOVE_NODE = "REMOVE_NODE"
    UPDATE_CONFIG = "UPDATE_CONFIG"
    ADD_EDGE = "ADD_EDGE"
    REMOVE_EDGE = "REMOVE_EDGE"
    AUTO_HEAL = "AUTO_HEAL"


class Operation(BaseModel):
    """
    修改图的原子操作。
    """
    op_type: OpType
    target_id: Optional[str] = Field(None, description="被操作的节点/连线 ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="操作参数（例如新节点类型、配置值）")


class BuilderContext(BaseModel):
    """
    Agent 构建过程的上下文。
    包含用户意图、当前图状态以及其他元数据。
    """
    user_prompt: str = Field(..., description="用户的自然语言提示词")
    current_graph: Optional[LogicalGraph] = Field(None, description="当前的图结构 (如果有)")
    model_config_id: Optional[int] = Field(None, description="模型配置 ID，用于获取 API Key 和 Base URL")
    agent_type: str = Field("builder", description="Agent 类型: 'builder' 或 'chat'")
    session_id: str = Field(None, description="当前会话 ID")
    auth_token: Optional[str] = Field(None, description="用户认证 Token (内部使用，不需前端传递)", exclude=True)
