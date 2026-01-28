package com.fastflow.entity.workflow;

import lombok.Data;

/**
 * 工作流VO
 */
@Data
public class WorkflowDTO {

    /**
     * 工作流名称
     */
    private String name;

    /**
     * 工作流描述
     */
    private String description;

    /**
     * 工作流配置JSON
     */
    private String config;

}
