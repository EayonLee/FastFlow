# syntax=docker/dockerfile:1.7
FROM python:3.10-bookworm

# =========================
# 基础环境变量
# =========================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    APP_HOST=0.0.0.0 \
    APP_PORT=9090 \
    TZ=Asia/Shanghai

# =========================
# 可配置构建参数
# - 仅使用腾讯云 PyPI 镜像源
# =========================
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple/
ARG PIP_INSTALL_RETRIES=5
ARG PIP_INSTALL_TIMEOUT=120
ARG INSTALL_UNSTRUCTURED=0

# =========================
# 创建最小权限运行账号
# =========================
RUN groupadd --system fastflow \
    && useradd --system --gid fastflow --create-home --home-dir /home/fastflow fastflow

# =========================
# 复制依赖文件
# 这里只复制 requirements.txt，便于最大化利用缓存
# =========================
COPY requirements.txt /tmp/requirements.txt

# =========================
# 第一步：生成运行时依赖清单
# 作用：
# 1. 去掉开发依赖：pytest / black / isort
# 2. 如果 INSTALL_UNSTRUCTURED != 1，则去掉 unstructured
# 输出：
#   /tmp/requirements.runtime.txt
# =========================
RUN set -eux; \
    awk 'BEGIN{IGNORECASE=1} !/^[[:space:]]*(pytest|black|isort)([<>=!~].*)?([[:space:]]*)$/' \
      /tmp/requirements.txt > /tmp/requirements.runtime.base.txt; \
    if [ "$INSTALL_UNSTRUCTURED" = "1" ]; then \
      cp /tmp/requirements.runtime.base.txt /tmp/requirements.runtime.txt; \
    else \
      awk 'BEGIN{IGNORECASE=1} !/^[[:space:]]*unstructured([<>=!~].*)?([[:space:]]*)$/' \
        /tmp/requirements.runtime.base.txt > /tmp/requirements.runtime.txt; \
    fi

# =========================
# 第二步：打印最终安装清单
# 方便构建日志中快速定位到底装了哪些包
# =========================
RUN set -eux; \
    cat /tmp/requirements.runtime.txt

# =========================
# 第三步：安装 Python 依赖
# - 仅使用腾讯云 PyPI 镜像源
# - 使用 BuildKit cache 加速重复构建
# - pip check 用于检测依赖冲突
# =========================
RUN --mount=type=cache,id=fastflow-nexus-base-pip,target=/root/.cache/pip,sharing=locked \
    set -eux; \
    pip install \
      --retries "${PIP_INSTALL_RETRIES}" \
      --timeout "${PIP_INSTALL_TIMEOUT}" \
      --prefer-binary \
      --no-compile \
      --progress-bar off \
      -r /tmp/requirements.runtime.txt \
      -i "${PIP_INDEX_URL}" \
      --trusted-host mirrors.cloud.tencent.com; \
    pip check

# =========================
# 第四步：清理临时文件
# =========================
RUN rm -f \
      /tmp/requirements.txt \
      /tmp/requirements.runtime.base.txt \
      /tmp/requirements.runtime.txt