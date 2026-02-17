package com.fastflow.entity.model;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 模型配置实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("model_configs")
public class ModelConfig {

    /**
     * 主键ID (自增)
     */
    @TableId(type = IdType.AUTO)
    private Long id;

    /**
     * 模型名称 (唯一)
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
     * API 密钥
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
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /**
     * 修改时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
