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
     * 模型ID
     */
    private String modelId;

    /**
     * API 密钥 (部分场景可能需要脱敏)
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
