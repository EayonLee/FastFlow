# syntax=docker/dockerfile:1.7
FROM fastflow-nexus-base:latest

# 复制项目源码到包目录，保持 `python -m nexus.main` 的导入路径
COPY --chown=fastflow:fastflow . /app/nexus

# 应用运行目录固定为项目根，确保相对路径（如 logs/）行为可预期
WORKDIR /app/nexus

USER fastflow

EXPOSE 9090

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/fastflow/nexus/v1/health', timeout=3)" || exit 1

ENTRYPOINT ["python", "-m", "nexus.main"]
