package com.fastflow.service.slash;

import com.fastflow.common.exception.BusinessException;
import com.fastflow.common.exception.ErrorCode;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Slash 目录代理服务。
 *
 * 核心职责：
 * 1) 调用 Nexus 的 slash catalog 接口；
 * 2) 规范化响应数据结构（统一提取 data 字段）；
 * 3) 将网络错误/配置错误转换为统一业务异常。
 */
@Service
public class SlashService {

    /**
     * JSON 解析器：用于解析 Nexus 返回体和错误体。
     */
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * HTTP 客户端：复用连接并统一超时策略，避免每次请求创建新实例。
     */
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .version(HttpClient.Version.HTTP_1_1)
            .build();

    /**
     * Nexus 服务基础地址（通过环境变量 NEXUS_BASE_URL 配置）。
     */
    @Value("${nexus.base-url:http://localhost:9090}")
    private String nexusBaseUrl;

    /**
     * 获取 slash 目录（skills + mcp 占位）。
     *
     * @param token 登录态令牌，透传给 Nexus 做鉴权
     * @return 目录数据对象，结构为 {skills: [...], mcp: [...]}
     */
    public Map<String, Object> getCatalog(String token) {
        // 1) 规范化 baseUrl，避免双斜杠或空字符串导致 URI 非法。
        String baseUrl = normalizeBaseUrl(nexusBaseUrl);

        // 2) 拼接 Nexus 目标接口地址。
        URI uri = URI.create(baseUrl + "/fastflow/nexus/v1/slash/catalog");

        // 3) 构造 GET 请求并透传 Authorization。
        HttpRequest request = HttpRequest.newBuilder(uri)
                .GET()
                .timeout(Duration.ofSeconds(10))
                .version(HttpClient.Version.HTTP_1_1)
                .header("Authorization", token == null ? "" : token)
                .build();

        try {
            // 4) 调用 Nexus 并读取字符串响应体。
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            int statusCode = response.statusCode();
            String body = response.body();

            // 5) 非 2xx 统一转为业务异常，并附带可读错误信息。
            if (statusCode < 200 || statusCode >= 300) {
                throw new BusinessException(
                        ErrorCode.SYSTEM_ERROR.getCode(),
                        "获取 Slash 目录失败：" + extractErrorMessage(body, statusCode)
                );
            }

            // 6) 解析响应结构：优先解包 data 字段，返回给控制器。
            return parseObjectMap(body);
        } catch (IOException e) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR.getCode(), "获取 Slash 目录失败：网络异常");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new BusinessException(ErrorCode.SYSTEM_ERROR.getCode(), "获取 Slash 目录失败：请求中断");
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR.getCode(), "获取 Slash 目录失败：服务地址配置错误");
        }
    }

    /**
     * 标准化 baseUrl：
     * - 去首尾空白
     * - 去掉尾部多余 '/'
     */
    private String normalizeBaseUrl(String baseUrl) {
        String normalized = String.valueOf(baseUrl == null ? "" : baseUrl).trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("nexus base-url is empty");
        }
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }

    /**
     * 解析响应体：
     * - 若存在顶层 data（统一返回体），优先返回 data 对象
     * - 否则直接返回顶层对象（兼容非统一格式）
     */
    private Map<String, Object> parseObjectMap(String body) throws IOException {
        if (body == null || body.isBlank()) {
            return new HashMap<>();
        }
        Map<String, Object> payload = objectMapper.readValue(body, new TypeReference<Map<String, Object>>() {});
        Object data = payload.get("data");
        if (data instanceof Map<?, ?> dataMap) {
            Map<String, Object> unwrapped = new HashMap<>();
            for (Map.Entry<?, ?> entry : dataMap.entrySet()) {
                if (entry.getKey() != null) {
                    unwrapped.put(String.valueOf(entry.getKey()), entry.getValue());
                }
            }
            return unwrapped;
        }
        return payload;
    }

    /**
     * 从错误响应体中提取可读 message，用于拼装异常信息。
     */
    private String extractErrorMessage(String body, int statusCode) {
        if (body == null || body.isBlank()) {
            return "HTTP " + statusCode;
        }
        try {
            Map<String, Object> payload = objectMapper.readValue(body, new TypeReference<Map<String, Object>>() {});
            Object message = payload.get("message");
            if (message != null && !String.valueOf(message).isBlank()) {
                return String.valueOf(message);
            }
        } catch (IOException ignored) {
            // ignore parse error and fallback raw body
        }
        return body;
    }
}
