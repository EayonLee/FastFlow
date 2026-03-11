FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

ENV TZ=Asia/Shanghai \
    JAVA_TOOL_OPTIONS="" \
    SPRING_PROFILES_ACTIVE=prod \
    SPRING_CONFIG_ADDITIONAL_LOCATION=optional:file:/app/config/

# 创建最小权限运行账号，避免容器内默认 root 运行
RUN groupadd --system fastflow && useradd --system --gid fastflow --create-home --home-dir /home/fastflow fastflow

# 运行镜像仅打包宿主机已构建好的产物：
COPY --chown=fastflow:fastflow target/api-1.0-SNAPSHOT.jar /app/app.jar

USER fastflow

EXPOSE 8080

VOLUME ["/app/config"]

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
