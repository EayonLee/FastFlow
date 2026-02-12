from typing import Optional

from pydantic import BaseModel, Field

from nexus.core.schemas.workflow_graph_schema import WorkflowGraph


class ChatRequestContext(BaseModel):
    """
    Agent 会话上下文。
    """

    user_prompt: str = Field(..., description="用户输入")
    workflow_graph: Optional[WorkflowGraph] = Field(None, description="当前工作流图结构")
    model_config_id: Optional[int] = Field(None, description="模型配置 ID")
    mode: str = Field("chat", description="Agent 类型: 'builder' 或 'chat'")
    session_id: str = Field(None, description="会话 ID")
    auth_token: Optional[str] = Field(None, description="用户认证 Token", exclude=True)
