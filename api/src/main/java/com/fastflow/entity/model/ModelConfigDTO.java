package com.fastflow.entity.model;

import lombok.Data;

/**
 * 模型配置DTO (数据传输对象)
 * 用于接收前端传递的创建或更新参数
 */
@Data
public class ModelConfigDTO {

    /**
     * 模型名称
     */
    private String modelName;

    /**
     * 模型ID
     */
    private String modelId;

    /**
     * API 密钥
     */
    private String apiKey;

    /**
     * API 基础地址
     */
    private String apiBase;

    /**
     * API 模式（如：openai、claude、google_gemini）
     */
    private String apiMode;

    /**
     * 所属用户组ID
     */
    private String userGroupId;
}
