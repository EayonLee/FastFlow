package com.fastflow.entity.model;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 模型配置VO (视图对象)
 * 用于返回给前端的展示数据
 */
@Data
public class ModelConfigVO {

    /**
     * 主键ID
     */
    private Long id;

    /**
     * 模型名称
     */
    private String modelName;

    /**
     * LiteLLM 模型标识（例如：moonshot/kimi-k2.5）
     */
    private String litellmModel;

    /**
     * LiteLLM provider（可选）
     */
    private String provider;

    /**
     * API 密钥 (返回时可按需脱敏)
     */
    private String apiKey;

    /**
     * API 网关地址（可选）
     */
    private String baseUrl;

    /**
     * LiteLLM 透传参数 JSON
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

    /**
     * 排序值（越小越靠前）
     */
    private Integer sortOrder;

    /**
     * 创建时间
     */
    private LocalDateTime createdAt;

    /**
     * 修改时间
     */
    private LocalDateTime updatedAt;
}
