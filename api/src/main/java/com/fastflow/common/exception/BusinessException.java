package com.fastflow.common.exception;

import lombok.Getter;

import java.util.Map;

@Getter
public class BusinessException extends RuntimeException {
    private final int code;
    private final Map<String, String> fieldErrors;

    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.code = errorCode.getCode();
        this.fieldErrors = null;
    }

    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
        this.fieldErrors = null;
    }

    public BusinessException(int code, String message, Map<String, String> fieldErrors) {
        super(message);
        this.code = code;
        this.fieldErrors = fieldErrors;
    }

    public BusinessException(String message) {
        super(message);
        this.code = -1; // Default error code
        this.fieldErrors = null;
    }
}
