from typing import Optional

from pydantic import BaseModel, Field

from nexus.core.schemas.workflow_graph_schema import WorkflowGraph


class WorkflowMeta(BaseModel):
    """
    工作流元信息（用于增强模型理解，不影响工作流图结构解析）。
    """

    workflow_name: Optional[str] = Field(None, description="工作流名称")
    workflow_description: Optional[str] = Field(None, description="工作流描述")


class ChatRequestContext(BaseModel):
    """
    Agent 会话上下文。
    """

    user_prompt: str = Field(..., description="用户输入")
    workflow_graph: Optional[WorkflowGraph] = Field(None, description="当前工作流图结构（支持对象或导出 JSON 字符串）")
    workflow_meta: Optional[WorkflowMeta] = Field(None, description="工作流元信息（名称、描述）")
    model_config_id: Optional[int] = Field(None, description="模型配置 ID")
    mode: str = Field("chat", description="Agent 类型: 'builder' 或 'chat'")
    session_id: Optional[str] = Field(None, description="会话 ID")
    auth_token: Optional[str] = Field(None, description="用户认证 Token", exclude=True)
