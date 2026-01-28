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
public class NodeDefVO {
    private String flowNodeType;
    private String name;
    private String icon;
    private String avatar;
    private String version;
    private String intro;
    private Map<String, Integer> position;
    @Builder.Default
    private List<NodeInputDefVO> inputs = Collections.emptyList();
    @Builder.Default
    private List<NodeOutputDefVO> outputs = Collections.emptyList();
    private String nodeId; 
}
