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
    APP_HOST: str = "0.0.0.0"
    APP_VERSION: str = "1.0.0"
    
    # FastFlow Nexus 服务端配置
    FASTFLOW_API_URL: str = "http://localhost:8080"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"
    LOG_OUTPUT: str = "console"
    LOG_FILE_PATH: Optional[str] = "logs/engine.log"
    LOG_COLORIZE: bool = True
    LOG_ROTATION: str = "1"
    LOG_RETENTION: str = "7"
    LOG_MAX_FILE_SIZE: str = "100"

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
