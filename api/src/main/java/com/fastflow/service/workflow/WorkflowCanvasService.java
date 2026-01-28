package com.fastflow.service.workflow;

import com.fastflow.entity.workflow.node.CanvasVO;
import com.fastflow.entity.workflow.node.NodeDefVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class WorkflowCanvasService {

    @Autowired
    private WorkflowNodeService workflowNodeService;


    /**
     * 获取默认工作流画布数据
     * 包含初始节点和连线
     *
     * @return CanvasVO
     */
    public CanvasVO getDefaultCanvas() {
        // 1. 创建节点
        NodeDefVO userGuide = workflowNodeService.createUserGuideNode();
        NodeDefVO startNode = workflowNodeService.createWorkflowStartNode();
        NodeDefVO chatNode = workflowNodeService.createChatNode();

        // 重新设置一下位置，使其在画布中居中显示
        // UserGuide (System Config)
        Map<String, Integer> pos1 = new HashMap<>();
        pos1.put("x", 0);
        pos1.put("y", 0);
        userGuide.setPosition(pos1);

        // Workflow Start
        Map<String, Integer> pos2 = new HashMap<>();
        pos2.put("x", 350);
        pos2.put("y", 0);
        startNode.setPosition(pos2);

        // Chat Node
        Map<String, Integer> pos3 = new HashMap<>();
        pos3.put("x", 700);
        pos3.put("y", 0);
        chatNode.setPosition(pos3);

        List<NodeDefVO> nodes = new ArrayList<>();
        nodes.add(userGuide);
        nodes.add(startNode);
        nodes.add(chatNode);

        // 2. 创建连线
        // Start -> Chat
        Map<String, Object> edge = new HashMap<>();
        edge.put("id", "e-start-chat");
        edge.put("source", startNode.getNodeId());
        edge.put("target", chatNode.getNodeId());
        edge.put("type", "tech"); // 前端自定义类型

        List<Object> edges = new ArrayList<>();
        edges.add(edge);

        return CanvasVO.builder()
                .nodes(nodes)
                .edges(edges)
                .build();
    }
}
