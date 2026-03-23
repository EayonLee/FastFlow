import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Nexus 服务配置类。
    自动加载 .env 文件中的配置。
    """
    
    # 服务配置
    APP_NAME: str = "FastFlow-Nexus"
    APP_PORT: int = 9090
    # 仅用于 Uvicorn 监听地址（bind host）。
    # 示例：
    # - 0.0.0.0: 监听所有网卡，允许外部访问
    # - 127.0.0.1: 仅本机访问
    # 注意：本项目已移除 TrustedHostMiddleware，APP_HOST 不再用于 Host Header 白名单校验。
    APP_HOST: str = "0.0.0.0"
    APP_VERSION: str = "1.0.0"
    
    # FastFlow Nexus 服务端配置
    FASTFLOW_API_URL: str = "http://localhost:8080"

    # 历史会话配置
    # 每个 session 最多保留的消息条数（短期记忆窗口）
    SESSION_HISTORY_MAX_MESSAGES: int = 10
    # 会话过期时间（秒）
    # <= 0 表示不过期，默认 1 小时
    SESSION_HISTORY_EXPIRE_SECONDS: int = 60 * 60

    # 工具调用策略配置
    # 单个用户问题允许执行的工具调用硬上限（防止失控循环）
    TOOL_MAX_CALLS_PER_QUESTION: int = 50
    # 工具循环检测：warning 阈值（仅告警，不熔断）
    TOOL_LOOP_WARNING_THRESHOLD: int = 10
    # 工具循环检测：critical 阈值（停止当前工具路径）
    TOOL_LOOP_CRITICAL_THRESHOLD: int = 20
    # 工具循环检测：global 阈值（停止本轮全部工具调用）
    TOOL_LOOP_GLOBAL_THRESHOLD: int = 30
    # 工具循环检测窗口：仅观察最近 N 次工具执行历史
    TOOL_LOOP_HISTORY_SIZE: int = 30

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"
    LOG_OUTPUT: str = "console"
    LOG_FILE_PATH: Optional[str] = "logs/engine.log"
    LOG_COLORIZE: bool = True
    LOG_ROTATION: str = "1"
    LOG_RETENTION: str = "7"
    LOG_MAX_FILE_SIZE: str = "100"
    
    # LiteLLM 日志配置（默认关闭调试输出，防止打印请求体/提示词）
    LITELLM_VERBOSE: bool = False
    LITELLM_SUPPRESS_DEBUG_INFO: bool = True
    LITELLM_TURN_OFF_MESSAGE_LOGGING: bool = True
    LITELLM_DISABLE_STREAMING_LOGGING: bool = True
    LITELLM_LOG_LEVEL: str = "WARNING"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

# 创建全局配置实例
try:
    settings = Settings()
except Exception as e:
    # Fallback default
    settings = Settings(_env_file=None)

def get_config() -> Settings:
    return settings
