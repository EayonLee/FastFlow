package com.fastflow.common.result;

import cn.hutool.core.util.StrUtil;
import com.fastflow.common.exception.ErrorCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;


@Setter
@Getter
@NoArgsConstructor
public class RestfulResult {

    /**
     * 状态码
     */
    private int code;

    /**
     * 操作描述信息数组
     */
    private String message;

    /**
     * 返回数据
     */
    private Object data;

    public RestfulResult(int code, String message, Object data) {
        this.code = code;
        this.message = message;
        this.data = data;
    }

    public static RestfulResult error(String message) {
        return error(ErrorCode.SYSTEM_ERROR.getCode(), message);
    }

    public static RestfulResult error(int code, String message) {
        return new RestfulResult(code, message, null);
    }


    public static RestfulResult success(String message) {
        return success(message, null);
    }

    public static RestfulResult success() {
        return success("Success", null);
    }

    public static RestfulResult success(Object data) {
        return success("Success", data);
    }


    public static RestfulResult success(String message, Object data) {
        return StrUtil.isNotBlank(message) ? new RestfulResult(200,
                message, data) : new RestfulResult(200,
                "Success", data);
    }

}
