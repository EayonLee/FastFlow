"""
基础时间工具。

提供与业务无关的时间能力：
- 按指定 format 输出当前系统时间
- 输出当前 Unix 时间戳（秒/毫秒）
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_TIME_FORMAT = "YYYY-MM-dd HH:mm:ss"
WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

TIME_FORMAT_TOKEN_MAP = (
    ("dddd", "%A"),
    ("ddd", "%a"),
    ("SSS", "{ms}"),
    ("sss", "{ms}"),
    ("YYYY", "%Y"),
    ("yyyy", "%Y"),
    ("YY", "%y"),
    ("yy", "%y"),
    ("MM", "%m"),
    ("DD", "%d"),
    ("dd", "%d"),
    ("HH", "%H"),
    ("hh", "%H"),
    ("mm", "%M"),
    ("ss", "%S"),
)
TIME_FORMAT_TOKEN_DICT = dict(TIME_FORMAT_TOKEN_MAP)
TIME_FORMAT_TOKENS = tuple(sorted(TIME_FORMAT_TOKEN_DICT.keys(), key=len, reverse=True))


def _translate_alpha_segment(segment: str) -> str:
    """
    仅当整段字母串可被格式 token 完整解析时才转换，否则按字面量保留。

    这样可以避免把普通单词（如 `address`）误替换成日期格式。
    """
    if not segment:
        return segment

    translated_parts: List[str] = []
    index = 0
    while index < len(segment):
        matched_token = None
        for token in TIME_FORMAT_TOKENS:
            if segment.startswith(token, index):
                matched_token = token
                break
        if not matched_token:
            return segment
        translated_parts.append(TIME_FORMAT_TOKEN_DICT[matched_token])
        index += len(matched_token)
    return "".join(translated_parts)


def _to_strftime_format(format_text: str) -> str:
    normalized_format = format_text or DEFAULT_TIME_FORMAT
    parts = re.split(r"([A-Za-z]+)", normalized_format)
    translated_parts = [
        _translate_alpha_segment(part) if index % 2 == 1 else part
        for index, part in enumerate(parts)
    ]
    return "".join(translated_parts)


class TimeTools:
    """
    基础时间工具实现。
    """

    def __init__(self, context: ChatRequestContext):
        self.context = context

    def get_current_time(self, format: str = DEFAULT_TIME_FORMAT, timezone: str = DEFAULT_TIMEZONE) -> str:
        """
        按给定格式返回当前时间。
        """
        normalized_timezone = (timezone or "").strip() or DEFAULT_TIMEZONE
        try:
            now = datetime.now(ZoneInfo(normalized_timezone))
        except ZoneInfoNotFoundError:
            error_result_json = json.dumps(
                {
                    "error": f"invalid timezone: {normalized_timezone}",
                    "timezone": normalized_timezone,
                },
                ensure_ascii=False,
            )
            logger.info("[执行工具失败] tool=get_current_time result=%s", error_result_json)
            return error_result_json

        normalized_format = (format or "").strip() or DEFAULT_TIME_FORMAT
        try:
            translated_format = _to_strftime_format(normalized_format)
            formatted_time = now.strftime(translated_format).replace("{ms}", f"{now.microsecond // 1000:03d}")
        except ValueError as error:
            error_result_json = json.dumps(
                {
                    "error": f"invalid datetime format: {normalized_format}",
                    "detail": str(error),
                },
                ensure_ascii=False,
            )
            logger.info("[执行工具失败] tool=get_current_time result=%s", error_result_json)
            return error_result_json

        result_json = json.dumps(
            {
                "formatted_time": formatted_time,
                "format": normalized_format,
                "timezone": normalized_timezone,
                "iso_time": now.isoformat(),
                "weekday_index": now.isoweekday(),
                "weekday_cn": WEEKDAY_CN[now.isoweekday() - 1],
                "weekday_en": now.strftime("%A"),
            },
            ensure_ascii=False,
        )
        logger.info("[执行工具成功] tool=get_current_time result=%s", result_json)
        return result_json

    def get_current_timestamp(self, timezone: str = DEFAULT_TIMEZONE) -> str:
        """
        返回当前 Unix 时间戳（秒与毫秒）。
        """
        normalized_timezone = (timezone or "").strip() or DEFAULT_TIMEZONE
        try:
            now = datetime.now(ZoneInfo(normalized_timezone))
        except ZoneInfoNotFoundError:
            error_result_json = json.dumps(
                {
                    "error": f"invalid timezone: {normalized_timezone}",
                    "timezone": normalized_timezone,
                },
                ensure_ascii=False,
            )
            logger.info("[执行工具失败] tool=get_current_timestamp result=%s", error_result_json)
            return error_result_json

        timestamp_seconds = int(now.timestamp())
        result_json = json.dumps(
            {
                "timestamp_seconds": timestamp_seconds,
                "timestamp_milliseconds": timestamp_seconds * 1000 + now.microsecond // 1000,
                "timezone": normalized_timezone,
                "iso_time": now.isoformat(),
                "weekday_index": now.isoweekday(),
                "weekday_cn": WEEKDAY_CN[now.isoweekday() - 1],
                "weekday_en": now.strftime("%A"),
            },
            ensure_ascii=False,
        )
        logger.info("[执行工具成功] tool=get_current_timestamp result=%s", result_json)
        return result_json


def build_time_tools(context: ChatRequestContext) -> Tuple[List, TimeTools]:
    """
    构建基础时间工具列表。
    """
    tool_impl = TimeTools(context)

    @tool
    def get_current_time(format: str = DEFAULT_TIME_FORMAT, timezone: str = DEFAULT_TIMEZONE):
        """
        在需要“当前系统时间”且希望指定输出格式时调用。
        `timezone` 默认为 `Asia/Shanghai`，可选传 IANA 时区（如 `UTC`、`America/New_York`）。
        `format` 支持常见格式 token，如 `YYYY-MM-dd`、`YYYY-MM-dd HH:mm:ss`、`YYYY/MM/dd HH:mm:ss.SSS`、`YYYY-MM-dd HH:mm:ss.sss`、`dddd`（Monday）、`ddd`（Mon）。
        token 说明：`MM`=月份，`dd`=日期，`HH`=小时（24h），`mm`=分钟，`ss`=秒，`SSS/sss`=毫秒。
        返回 `formatted_time`、`format`、`timezone`、`iso_time`、`weekday_index`、`weekday_cn`、`weekday_en`。
        """
        return tool_impl.get_current_time(format, timezone)

    @tool
    def get_current_timestamp(timezone: str = DEFAULT_TIMEZONE):
        """
        在需要当前 Unix 时间戳时调用。
        `timezone` 默认为 `Asia/Shanghai`，可选传 IANA 时区（如 `UTC`、`America/New_York`）。
        返回 `timestamp_seconds`（秒）与 `timestamp_milliseconds`（毫秒）以及时区信息。
        """
        return tool_impl.get_current_timestamp(timezone)

    return [get_current_time, get_current_timestamp], tool_impl


__all__ = ["TimeTools", "build_time_tools"]
