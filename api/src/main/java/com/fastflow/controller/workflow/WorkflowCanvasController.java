package com.fastflow.controller.workflow;

import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.result.RestfulResult;
import com.fastflow.service.workflow.WorkflowCanvasService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/workflow/canvas")
public class WorkflowCanvasController {

    @Autowired
    private WorkflowCanvasService workflowCanvasService;

    /**
     * 获取默认工作流画布配置
     *
     * @return RestfulResult<CanvasVO>
     */
    @GetMapping("/init")
    public RestfulResult getDefaultCanvas() {
        return RestfulResult.success(workflowCanvasService.getDefaultCanvas());
    }

}
