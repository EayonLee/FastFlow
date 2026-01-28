package com.fastflow.entity.workflow;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 工作流实体类
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("workflows")
public class Workflow {

    /**
     * 工作流ID
     */
    @TableId(type = IdType.INPUT)
    private String id;

    /**
     * 工作流名称
     */
    private String name;

    /**
     * 工作流描述
     */
    private String description;

    /**
     * 创建者UID
     */
    private Long creator;

    /**
     * 工作流配置JSON
     */
    private String config;

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
