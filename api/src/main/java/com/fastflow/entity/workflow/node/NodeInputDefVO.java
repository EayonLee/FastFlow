package com.fastflow.entity.workflow.node;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NodeInputDefVO {
    @Builder.Default
    private String key = "";
    @Builder.Default
    private String valueType = "";
    @Builder.Default
    private String label = "";
    @Builder.Default
    private boolean isPro = false;
    @Builder.Default
    private List<String> renderTypeList = Collections.singletonList("hidden");
    private Object value; // Can be null or object
    @Builder.Default
    private boolean required = false;
    private String llmModelType;
    @Builder.Default
    private String toolDescription = "";
    @Builder.Default
    private String debugLabel = "";
    private Double min;
    private Double max;
    private Double step;
    private String description;
    private String placeholder;
    private Map<String, Object> customInputConfig;
    @Builder.Default
    private boolean canEdit = false;
    private String valueDesc;
    @Builder.Default
    private Integer selectedTypeIndex = 0;
    private Object selected;
}
