import logging
import json
import sys
import re
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger as loguru_logger

from config.config import get_config

settings = get_config()

class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)

class TextFormatter(logging.Formatter):
    """文本格式日志格式化器"""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

def parse_size(size_str: str) -> int:
    """解析大小字符串，返回字节数"""
    size_str = size_str.strip().upper()
    
    # 提取数字和单位
    match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGT]?B?)', size_str)
    if not match:
        # 如果没有单位，默认为MB
        try:
            return int(float(size_str)) * 1024 * 1024
        except ValueError:
            return 100 * 1024 * 1024  # 默认100MB
    
    number, unit = match.groups()
    number = float(number)
    
    # 单位转换
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024,
        'TB': 1024 * 1024 * 1024 * 1024,
        'K': 1024,
        'M': 1024 * 1024,
        'G': 1024 * 1024 * 1024,
        'T': 1024 * 1024 * 1024 * 1024,
        '': 1024 * 1024  # 默认MB
    }
    
    return int(number * multipliers.get(unit, 1024 * 1024))

def setup_logging():
    """设置日志配置"""
    
    # 移除loguru的默认处理器
    loguru_logger.remove()
    
    # 根据LOG_OUTPUT配置决定输出方式
    log_output = settings.LOG_OUTPUT.lower()
    
    # 设置日志格式
    if settings.LOG_FORMAT.lower() == "json":
        log_format = (
            '{"timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
            '"level": "{level}", '
            '"logger": "{name}", '
            '"message": "{message}", '
            '"module": "{module}", '
            '"function": "{function}", '
            '"line": {line}}'
        )
    else:
        log_format = "{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}"
    
    # 控制台处理器
    if log_output in ["console", "both"]:
        loguru_logger.add(
            sys.stdout,
            format=log_format,
            level=settings.LOG_LEVEL.upper(),
            colorize=settings.LOG_COLORIZE,
            backtrace=True,
            diagnose=True
        )
    
    # 文件处理器
    if log_output in ["file", "both"] and settings.LOG_FILE_PATH:
        log_file_path = Path(settings.LOG_FILE_PATH)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 解析配置参数
        rotation_config = settings.LOG_ROTATION
        retention_config = settings.LOG_RETENTION
        max_size = parse_size(settings.LOG_MAX_FILE_SIZE)
        
        # 处理rotation配置
        if rotation_config.isdigit():
            rotation = f"{rotation_config} days"
        else:
            rotation = rotation_config
        
        # 处理retention配置
        if retention_config.isdigit():
            retention = f"{retention_config} days"
        else:
            retention = retention_config
        
        loguru_logger.add(
            log_file_path,
            format=log_format,
            level=settings.LOG_LEVEL.upper(),
            rotation=max_size,  # 按大小轮转
            retention=retention,  # 保留时间
            compression="gz",  # 压缩旧日志
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )
        
        # 如果配置了时间轮转，添加额外的时间轮转处理器
        if "day" in rotation.lower() or "hour" in rotation.lower():
            loguru_logger.add(
                str(log_file_path).replace(".log", "_{time:YYYY-MM-DD}.log"),
                format=log_format,
                level=settings.LOG_LEVEL.upper(),
                rotation=rotation,  # 按时间轮转
                retention=retention,
                compression="gz",
                encoding="utf-8",
                backtrace=True,
                diagnose=True
            )
    
    # 设置标准库日志与loguru的互操作
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # 获取对应的loguru级别
            try:
                level = loguru_logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            
            # 查找调用者
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            
            loguru_logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )
    
    # 设置标准库日志器使用loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # 设置第三方库日志级别
    for logger_name in ["uvicorn", "uvicorn.access", "transformers"]:
        logging.getLogger(logger_name).setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # 应用日志器使用配置文件级别
    app_logger = logging.getLogger("app")
    app_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    # 返回一个包装了loguru的标准库日志器
    logger = logging.getLogger(name)
    return logger

class LoggerAdapter(logging.LoggerAdapter):
    """日志适配器，支持添加额外字段"""
    
    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        """处理日志消息，添加额外字段"""
        if "extra" not in kwargs:
            kwargs["extra"] = {}
        
        # 合并额外字段
        kwargs["extra"].update(self.extra)
        
        # 添加到record的extra_fields属性
        if "extra_fields" not in kwargs["extra"]:
            kwargs["extra"]["extra_fields"] = {}
        kwargs["extra"]["extra_fields"].update(self.extra)
        
        return msg, kwargs

