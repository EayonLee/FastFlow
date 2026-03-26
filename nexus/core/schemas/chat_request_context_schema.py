from typing import Optional

from pydantic import BaseModel, Field, field_validator

from nexus.core.schemas.workflow_graph_schema import WorkflowGraph


class WorkflowMeta(BaseModel):
    """
    工作流元信息（用于增强模型理解，不影响工作流图结构解析）。
    """

    workflow_name: Optional[str] = Field(None, description="工作流名称")
    workflow_description: Optional[str] = Field(None, description="工作流描述")


class ExecutionHints(BaseModel):
    """
    前端显式传入的工具选择信号。

    这些字段属于应用协议，不应再混入 `user_prompt` 文本里交给模型理解。
    """

    selected_nodes: list[str] = Field(default_factory=list, description="当前显式选中的节点 ID 列表")
    selected_skills: list[str] = Field(default_factory=list, description="当前显式选中的 skill 名称列表")

    @field_validator("selected_nodes", "selected_skills", mode="before")
    @classmethod
    def _normalize_string_list(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("execution_hints fields must be arrays")
        normalized_values: list[str] = []
        for item in value:
            normalized_item = str(item or "").strip()
            if normalized_item:
                normalized_values.append(normalized_item)
        return normalized_values

    def has_items(self) -> bool:
        return bool(self.selected_nodes or self.selected_skills)

    def summary(self) -> dict[str, int]:
        return {
            "selected_node_count": len(self.selected_nodes),
            "selected_skill_count": len(self.selected_skills),
        }


class ChatRequestContext(BaseModel):
    """
    Agent 会话上下文。
    """

    user_prompt: str = Field(..., description="用户输入")
    workflow_graph: Optional[WorkflowGraph] = Field(None, description="当前工作流图结构（支持对象或导出 JSON 字符串）")
    workflow_meta: Optional[WorkflowMeta] = Field(None, description="工作流元信息（名称、描述）")
    execution_hints: ExecutionHints = Field(default_factory=ExecutionHints, description="前端显式传入的工具选择信号")
    model_config_id: Optional[int] = Field(None, description="模型配置 ID")
    mode: str = Field("chat", description="Agent 类型: 'chat'、'builder' 或 'debugger'（SOLO Debugger）")
    session_id: Optional[str] = Field(None, description="会话 ID")
    request_id: Optional[str] = Field(None, description="单次请求 ID")
    auth_token: Optional[str] = Field(None, description="用户认证 Token", exclude=True)


class ChatCancelRequest(BaseModel):
    """显式取消单次 chat 请求。"""

    session_id: str = Field(..., description="会话 ID")
    request_id: str = Field(..., description="单次请求 ID")
