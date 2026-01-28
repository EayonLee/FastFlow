package com.fastflow.entity.workflow.node;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NodeOutputDefVO {
    @Builder.Default
    private String id = "";
    @Builder.Default
    private String key = "";
    @Builder.Default
    private String label = "";
    @Builder.Default
    private String type = "static";
    @Builder.Default
    private String valueType = "";
    @Builder.Default
    private String description = "";
    @Builder.Default
    private String valueDesc = "";
    @Builder.Default
    private boolean required = false;
    @Builder.Default
    private Map<String, Object> customFieldConfig = new java.util.HashMap<>();
}
