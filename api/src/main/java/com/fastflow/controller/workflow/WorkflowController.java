package com.fastflow.controller.workflow;

import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.result.RestfulResult;
import com.fastflow.entity.user.UserInfo;
import com.fastflow.entity.workflow.WorkflowDTO;
import com.fastflow.service.workflow.WorkflowService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;


/**
 * 工作流管理接口控制器
 */
@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/workflow")
public class WorkflowController {

    @Autowired
    private WorkflowService workflowService;


    /**
     * 查询单个工作流详情
     *
     * @param userInfo 当前登录用户信息
     * @param id       工作流 ID
     * @return RestfulResult<WorkflowVO>
     */
    @GetMapping("/{id}")
    public RestfulResult getWorkflow(@RequestAttribute("userInfo") UserInfo userInfo, @PathVariable("id") String id) {
        return RestfulResult.success(workflowService.getWorkflow(userInfo, id));
    }

    /**
     * 查询当前用户的工作流列表
     * <p>
     * 返回的列表中不包含 config 详情，只有基础信息
     *
     * @param userInfo 当前登录用户信息
     * @return RestfulResult<List<WorkflowVO>>
     */
    @GetMapping("/list")
    public RestfulResult getWorkflowList(@RequestAttribute("userInfo") UserInfo userInfo) {
        return RestfulResult.success(workflowService.getWorkflowList(userInfo));
    }

    /**
     * 创建一个新的工作流
     *
     * @param userInfo 当前登录用户信息
     * @param workflow 创建请求体
     * @return RestfulResult<String> 返回新创建的工作流 ID
     */
    @PostMapping("/create")
    public RestfulResult createWorkflow(@RequestAttribute("userInfo") UserInfo userInfo,
                                        @RequestBody WorkflowDTO workflow) {
        return RestfulResult.success(workflowService.createWorkflow(userInfo, workflow));
    }

    /**
     * 更新工作流信息
     *
     * @param userInfo 当前登录用户信息
     * @param id       工作流 ID
     * @param workflow 更新请求体 (DTO)
     * @return RestfulResult
     */
    @PutMapping("/update/{id}")
    public RestfulResult updateWorkflow(@RequestAttribute("userInfo") UserInfo userInfo,
                                        @PathVariable("id") String id,
                                        @RequestBody WorkflowDTO workflow) {
        workflowService.updateWorkflow(userInfo, id, workflow);
        return RestfulResult.success();
    }

    /**
     * 删除指定的工作流
     *
     * @param userInfo 当前登录用户信息
     * @param id       工作流 ID
     * @return RestfulResult
     */
    @DeleteMapping("/delete/{id}")
    public RestfulResult deleteWorkflow(@RequestAttribute("userInfo") UserInfo userInfo,
                                        @PathVariable("id") String id) {
        workflowService.deleteWorkflow(userInfo, id);
        return RestfulResult.success();
    }
}
