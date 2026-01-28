package com.fastflow.controller.workflow;

import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.result.RestfulResult;
import com.fastflow.service.workflow.WorkflowNodeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;



/**
 * 工作流节点管理接口控制器
 * 
 * 主要功能：
 * 1. 提供工作流节点定义的查询接口
 * 2. 供前端获取可用的工作流节点列表（包括 UserGuide, WorkflowStart, ChatNode 等）
 */
@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/workflow/node")
public class WorkflowNodeController {

    @Autowired
    private WorkflowNodeService workflowNodeService;

    /**
     * 获取工作流节点定义列表
     *
     * @return RestfulResult<List<NodeDefVO>>
     */
    @GetMapping("/list")
    public RestfulResult getWorkflowNodeList() {
        return RestfulResult.success(workflowNodeService.getWorkflowNodeList());
    }
}
