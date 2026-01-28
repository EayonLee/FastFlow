package com.fastflow.entity.workflow.node;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 工作流画布数据对象
 * 包含节点和连线信息
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CanvasVO {
    private List<NodeDefVO> nodes;
    private List<Object> edges; // 使用 Object 是因为 Edge 的结构比较灵活，或者也可以定义 EdgeVO
}
