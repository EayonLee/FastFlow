# syntax=docker/dockerfile:1.7
FROM python:3.10-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    APP_HOST=0.0.0.0 \
    APP_PORT=9090 \
    TZ=Asia/Shanghai

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
ARG PIP_EXTRA_INDEX_URL=https://pypi.org/simple
ARG INSTALL_UNSTRUCTURED=0

# 创建最小权限运行账号
RUN groupadd --system fastflow && useradd --system --gid fastflow --create-home --home-dir /home/fastflow fastflow

# 预装 Python 运行时依赖：
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,id=fastflow-nexus-base-pip,target=/root/.cache/pip,sharing=locked \
    set -eux; \
    awk 'BEGIN{IGNORECASE=1} !/^[[:space:]]*(pytest|black|isort)([<>=!~].*)?([[:space:]]*)$/' /tmp/requirements.txt > /tmp/requirements.runtime.base.txt; \
    if [ "$INSTALL_UNSTRUCTURED" = "1" ]; then \
      cp /tmp/requirements.runtime.base.txt /tmp/requirements.runtime.txt; \
    else \
      awk 'BEGIN{IGNORECASE=1} !/^[[:space:]]*unstructured([<>=!~].*)?([[:space:]]*)$/' /tmp/requirements.runtime.base.txt > /tmp/requirements.runtime.txt; \
    fi; \
    pip install --retries 10 --timeout 120 \
      -r /tmp/requirements.runtime.txt \
      -i "${PIP_INDEX_URL}" \
      --extra-index-url "${PIP_EXTRA_INDEX_URL}" \
      --trusted-host "${PIP_TRUSTED_HOST}"; \
    rm -f /tmp/requirements.txt /tmp/requirements.runtime.base.txt /tmp/requirements.runtime.txt
