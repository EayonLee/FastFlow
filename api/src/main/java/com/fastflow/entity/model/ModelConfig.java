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
     * 模型ID
     */
    private String modelId;

    /**
     * API 密钥 (加密)
     */
    private String apiKey;

    /**
     * API 地址
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
