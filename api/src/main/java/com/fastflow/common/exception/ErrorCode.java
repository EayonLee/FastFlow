package com.fastflow.common.exception;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum ErrorCode {
    // 系统级错误
    SYSTEM_ERROR(-1, "系统繁忙，请稍后重试"),
    PARAM_ERROR(400, "参数错误"),
    NOT_LOGIN(401, "未登录或登录已过期"),
    FORBIDDEN(403, "无权限访问"),

    // 用户模块错误 10001 - 19999
    USER_NAME_ALREADY_EXISTS(10001, "用户名已存在"),
    USER_REGISTRATION_FAILED(10002, "用户注册失败"),
    USER_NOT_FOUND(10003, "用户不存在"),
    USER_PASSWORD_ERROR(10004, "用户名或密码错误"),
    USER_ACCOUNT_LOCKED(10005, "账号已被封禁"),
    USER_EMAIL_ALREADY_EXISTS(10006, "该邮箱已被注册"),
    ;

    private final int code;
    private final String message;
}
