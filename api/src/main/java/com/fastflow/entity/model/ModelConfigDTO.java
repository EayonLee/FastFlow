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
     * 模型标识（例如：moonshot/kimi-k2.5）
     */
    private String modelId;

    /**
     * LiteLLM provider（可选）
     */
    private String provider;

    /**
     * API 密钥（必填）
     */
    private String apiKey;

    /**
     * API 网关地址（可选）
     */
    private String baseUrl;

    /**
     * LiteLLM 透传参数 JSON（可选）
     */
    private String modelParamsJson;

    /**
     * 启用开关：true=可对外使用，false=禁用
     */
    private Boolean enabled;

    /**
     * 所属用户组ID
     */
    private String userGroupId;

}
