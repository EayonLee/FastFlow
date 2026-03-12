# syntax=docker/dockerfile:1.7
FROM fastflow-nexus-base:latest

# 复制 nexus 源码到包目录，配合基镜像中的 PYTHONPATH=/app，
COPY --chown=fastflow:fastflow . /app/nexus

WORKDIR /app

USER fastflow

EXPOSE 9090

ENTRYPOINT ["python", "-m", "nexus.main"]
