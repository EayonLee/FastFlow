from enum import Enum
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field, model_validator
from pydantic.config import ConfigDict


# --- Graph Structures ---

class NodeDefinition(BaseModel):
    """
    Registry 可用的节点类型定义。
    字段与 Nexus 返回的 NodeDefVO 对齐。
    """
    model_config = ConfigDict(populate_by_name=True)

    flow_node_type: str = Field(..., alias="flowNodeType")
    name: str
    icon: Optional[str] = None
    avatar: Optional[str] = None
    version: Optional[str] = None
    intro: Optional[str] = None
    position: Optional[Dict[str, Any]] = None
    inputs: List[Dict[str, Any]] = Field(default_factory=list)
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    node_id: Optional[str] = Field(None, alias="nodeId")


class NodeInstance(BaseModel):
    """
    图中节点的具体实例。
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(..., description="唯一的实例 ID", alias="nodeId")
    type: str = Field(..., description="必须匹配 NodeDefinition.type", alias="flowNodeType")
    # 所有节点原始字段统一收敛在 data (原 config)，与 Vue Flow 标准对齐
    data: Dict[str, Any] = Field(default_factory=dict, description="节点完整结构（前端传入的标准配置）")


class EdgeInstance(BaseModel):
    """
    两个节点之间的连接。
    """
    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    source_handle: Optional[str] = Field(None, alias="sourceHandle")
    target_handle: Optional[str] = Field(None, alias="targetHandle")


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
    UPDATE_INPUTS = "UPDATE_INPUTS"
    ADD_EDGE = "ADD_EDGE"
    REMOVE_EDGE = "REMOVE_EDGE"
    AUTO_HEAL = "AUTO_HEAL"


class AddNodeParams(BaseModel):
    """新增节点参数。"""
    type: str = Field(..., description="节点类型，必须来自节点定义")
    id: Optional[str] = Field(None, description="节点 ID，缺省由系统生成")
    label: Optional[str] = Field(None, description="节点显示名")
    name: Optional[str] = Field(None, description="节点名称")
    intro: Optional[str] = Field(None, description="节点简介")
    avatar: Optional[str] = Field(None, description="节点图标")
    version: Optional[str] = Field(None, description="节点版本")
    position: Optional[Dict[str, float]] = Field(None, description="节点位置")
    inputs: List[Dict[str, Any]] = Field(default_factory=list)
    outputs: List[Dict[str, Any]] = Field(default_factory=list)


class RemoveNodeParams(BaseModel):
    """删除节点参数。"""
    id: Optional[str] = Field(None, description="节点 ID，优先使用 target_id")


class AddEdgeParams(BaseModel):
    """新增连线参数。"""
    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


class RemoveEdgeParams(BaseModel):
    """删除连线参数。"""
    source: str = Field(..., description="源节点 ID")
    target: str = Field(..., description="目标节点 ID")
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


class InputValueUpdate(BaseModel):
    """输入值更新项。"""
    key: str = Field(..., description="输入字段 key")
    value: Any = Field(..., description="要写入的值")


class UpdateInputsParams(BaseModel):
    """更新节点输入值。"""
    inputs: List[InputValueUpdate] = Field(..., description="输入项列表（key/value）")


class AutoHealParams(BaseModel):
    """自动修复参数。"""
    strategy: Literal["minimal", "safe"] = Field("safe", description="修复策略")


class Operation(BaseModel):
    """
    修改图的原子操作。
    """
    op_id: Optional[str] = Field(None, description="操作 ID，便于追踪/回放")
    op_type: OpType
    target_id: Optional[str] = Field(None, description="被操作的节点/连线 ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="操作参数（例如新节点类型、输入值）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @model_validator(mode="after")
    def validate_params(self):
        """根据操作类型校验参数结构，确保最小可执行性。"""
        if self.op_type == OpType.ADD_NODE:
            validated = AddNodeParams.model_validate(self.params)
            self.params = validated.model_dump()
        elif self.op_type == OpType.REMOVE_NODE:
            validated = RemoveNodeParams.model_validate(self.params)
            if not self.target_id and not validated.id:
                raise ValueError("REMOVE_NODE requires target_id or params.id")
            self.params = validated.model_dump()
        elif self.op_type == OpType.ADD_EDGE:
            validated = AddEdgeParams.model_validate(self.params)
            self.params = validated.model_dump()
        elif self.op_type == OpType.REMOVE_EDGE:
            validated = RemoveEdgeParams.model_validate(self.params)
            self.params = validated.model_dump()
        elif self.op_type == OpType.UPDATE_INPUTS:
            validated = UpdateInputsParams.model_validate(self.params)
            if not self.target_id:
                raise ValueError("UPDATE_INPUTS requires target_id")
            self.params = validated.model_dump()
        elif self.op_type == OpType.AUTO_HEAL:
            validated = AutoHealParams.model_validate(self.params or {})
            self.params = validated.model_dump()
        return self


class OperationError(BaseModel):
    code: Literal[
        "MISSING_NODE_TYPE",
        "NODE_NOT_FOUND",
        "EDGE_NOT_FOUND",
        "INVALID_OP"
    ]
    message: str
    op_id: Optional[str] = None
    target_id: Optional[str] = None


class ApplyResult(BaseModel):
    graph: LogicalGraph
    errors: List[OperationError] = Field(default_factory=list)
    applied_ops: int = 0


class BuilderContext(BaseModel):
    """
    Agent 构建过程的上下文。
    包含用户意图、当前图状态以及其他元数据。
    """
    user_prompt: str = Field(..., description="用户的自然语言提示词")
    current_graph: Optional[LogicalGraph] = Field(None, description="当前的图结构 (如果有)")
    model_config_id: Optional[int] = Field(None, description="模型配置 ID，用于获取 Nexus Key 和 Base URL")
    agent_type: str = Field("builder", description="Agent 类型: 'builder' 或 'chat'")
    session_id: str = Field(None, description="当前会话 ID")
    auth_token: Optional[str] = Field(None, description="用户认证 Token (内部使用，不需前端传递)", exclude=True)
