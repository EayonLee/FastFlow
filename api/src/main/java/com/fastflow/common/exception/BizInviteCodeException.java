package com.fastflow.common.exception;

import lombok.Getter;

import java.util.Map;

@Getter
public class BizInviteCodeException extends RuntimeException {

    private static final String FIELD_NAME = "inviteCode";

    private final int code;
    private final Map<String, String> fieldErrors;

    private BizInviteCodeException(ErrorCode errorCode, String fieldMessage) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
        this.fieldErrors = Map.of(FIELD_NAME, fieldMessage);
    }

    public static BizInviteCodeException empty() {
        return new BizInviteCodeException(ErrorCode.USER_INVITE_CODE_EMPTY, "邀请码不能为空");
    }

    public static BizInviteCodeException formatError() {
        return new BizInviteCodeException(ErrorCode.USER_INVITE_CODE_FORMAT_ERROR, "邀请码必须是6位字母或数字");
    }

    public static BizInviteCodeException notFound() {
        return new BizInviteCodeException(ErrorCode.USER_INVITE_CODE_NOT_FOUND, "邀请码不存在");
    }

    public static BizInviteCodeException used() {
        return new BizInviteCodeException(ErrorCode.USER_INVITE_CODE_USED, "邀请码已被使用");
    }
}
