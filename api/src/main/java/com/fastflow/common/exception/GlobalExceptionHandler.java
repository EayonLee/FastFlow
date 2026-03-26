package com.fastflow.common.exception;

import com.fastflow.common.result.RestfulResult;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;


/**
 * 全局异常处理器
 * 
 * 主要功能：
 * 1. 捕获业务异常 (BusinessException) 并返回统一错误响应
 * 2. 捕获参数校验异常 (MethodArgumentNotValidException) 并返回详细错误信息
 * 3. 捕获兜底系统异常 (Exception) 防止堆栈信息泄露
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {


    /**
     * 处理邀请码业务异常
     *
     * @param e 邀请码业务异常
     * @return RestfulResult 包含邀请码专属错误码和字段错误信息
     */
    @ExceptionHandler(BizInviteCodeException.class)
    public RestfulResult handleBizInviteCodeException(BizInviteCodeException e) {
        return RestfulResult.error(e.getCode(), e.getMessage(), Map.of("fieldErrors", e.getFieldErrors()));
    }


    /**
     * 处理业务异常
     *
     * @param e 业务异常
     * @return RestfulResult 包含错误码和错误信息
     */
    @ExceptionHandler(BusinessException.class)
    public RestfulResult handleBusinessException(BusinessException e) {
        if (e.getFieldErrors() != null && !e.getFieldErrors().isEmpty()) {
            return RestfulResult.error(e.getCode(), e.getMessage(), Map.of("fieldErrors", e.getFieldErrors()));
        }
        return RestfulResult.error(e.getCode(), e.getMessage());
    }


    /**
     * 处理参数校验异常
     *
     * @param e 参数校验异常
     * @return RestfulResult 包含所有校验失败的字段信息
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public RestfulResult handleValidException(MethodArgumentNotValidException e) {
        BindingResult bindingResult = e.getBindingResult();
        String message = bindingResult.getAllErrors().stream()
                .map(error -> error.getDefaultMessage())
                .collect(Collectors.joining("; "));
        Map<String, String> fieldErrors = new LinkedHashMap<>();
        for (FieldError fieldError : bindingResult.getFieldErrors()) {
            fieldErrors.putIfAbsent(fieldError.getField(), fieldError.getDefaultMessage());
        }
        log.warn("Parameter validation error: {}", message);
        return RestfulResult.error(400, message, Map.of("fieldErrors", fieldErrors));
    }

    /**
     * 处理静态资源不存在异常（例如请求 "/."）。
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public RestfulResult handleNoResourceFoundException(NoResourceFoundException e, HttpServletRequest request) {
        log.warn(
                "No static resource. request=\"{} {} {}\" remote_addr={} x_forwarded_for=\"{}\" user_agent=\"{}\" resource_path={}",
                request.getMethod(),
                request.getRequestURI(),
                request.getProtocol(),
                safeValue(request.getRemoteAddr()),
                safeValue(request.getHeader("X-Forwarded-For")),
                safeValue(request.getHeader("User-Agent")),
                safeValue(e.getResourcePath())
        );
        return RestfulResult.error(404, "资源不存在");
    }

    /**
     * 处理其他未捕获的系统异常
     *
     * @param e 系统异常
     * @return RestfulResult 统一返回系统繁忙提示
     */
    @ExceptionHandler(Exception.class)
    public RestfulResult handleException(Exception e) {
        log.error(e.getMessage(), e);
        return RestfulResult.error(-1, "系统繁忙，请稍后重试");
    }

    private String safeValue(String value) {
        if (value == null || value.isBlank()) {
            return "-";
        }
        return value;
    }
}
