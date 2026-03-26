package com.fastflow.common.interceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 访问日志拦截器。
 *
 * 记录请求行、状态码、耗时、User-Agent 与 X-Forwarded-For，
 * 用于快速定位异常探测来源（例如误打 "/." 或 "/" 的调用方）。
 */
@Slf4j
@Component
public class AccessLogInterceptor implements HandlerInterceptor {

    private static final String START_TIME_ATTR = AccessLogInterceptor.class.getName() + ".start";

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        request.setAttribute(START_TIME_ATTR, System.currentTimeMillis());
        return true;
    }

    @Override
    public void afterCompletion(
            HttpServletRequest request,
            HttpServletResponse response,
            Object handler,
            Exception ex
    ) {
        long startedAt = extractStartTime(request);
        long elapsedMs = Math.max(0L, System.currentTimeMillis() - startedAt);
        String requestLine = buildRequestLine(request);
        String userAgent = headerOrDash(request, "User-Agent");
        String xForwardedFor = headerOrDash(request, "X-Forwarded-For");
        String remoteAddr = valueOrDash(request.getRemoteAddr());

        if (ex == null) {
            log.info(
                    "[Access] request=\"{}\" status={} remote_addr={} x_forwarded_for=\"{}\" user_agent=\"{}\" elapsed_ms={}",
                    requestLine,
                    response.getStatus(),
                    remoteAddr,
                    xForwardedFor,
                    userAgent,
                    elapsedMs
            );
            return;
        }

        log.warn(
                "[Access] request=\"{}\" status={} remote_addr={} x_forwarded_for=\"{}\" user_agent=\"{}\" elapsed_ms={} exception={}",
                requestLine,
                response.getStatus(),
                remoteAddr,
                xForwardedFor,
                userAgent,
                elapsedMs,
                ex.getClass().getSimpleName()
        );
    }

    private long extractStartTime(HttpServletRequest request) {
        Object startedAt = request.getAttribute(START_TIME_ATTR);
        if (startedAt instanceof Long value) {
            return value;
        }
        return System.currentTimeMillis();
    }

    private String buildRequestLine(HttpServletRequest request) {
        String queryString = request.getQueryString();
        String uri = request.getRequestURI();
        if (queryString != null && !queryString.isBlank()) {
            uri = uri + "?" + queryString;
        }
        return request.getMethod() + " " + uri + " " + request.getProtocol();
    }

    private String headerOrDash(HttpServletRequest request, String headerName) {
        return valueOrDash(request.getHeader(headerName));
    }

    private String valueOrDash(String value) {
        if (value == null || value.isBlank()) {
            return "-";
        }
        return value;
    }
}
