package com.fastflow.common.enums;

import lombok.Getter;

@Getter
public enum WorkflowType {
    USER_GUIDE("userGuide", "系统配置"),
    WORKFLOW_START("workflowStart", "流程开始"),
    CHAT_NODE("chatNode", "大模型会话");

    private final String type;
    private final String description;

    WorkflowType(String type, String description) {
        this.type = type;
        this.description = description;
    }

    public static WorkflowType getByType(String type) {
        for (WorkflowType workflowType : values()) {
            if (workflowType.getType().equals(type)) {
                return workflowType;
            }
        }
        return null;
    }
}
