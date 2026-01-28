package com.fastflow.controller;

import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.result.RestfulResult;
import com.fastflow.entity.model.ModelConfigDTO;
import com.fastflow.service.ModelConfigService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;


/**
 * 模型配置管理接口控制器
 *
 * 主要功能：
 * 1. 提供模型配置的增删改查 RESTful API
 * 2. 统一处理用户鉴权（@LoginCheck）
 */
@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/model_config")
public class ModelConfigController {

    @Autowired
    private ModelConfigService modelConfigService;

    /**
     * 获取所有模型配置列表
     *
     * @return RestfulResult<List<ModelConfigVO>>
     */
    @GetMapping("/list")
    public RestfulResult getModelConfigList() {
        return RestfulResult.success("Success", modelConfigService.getModelConfigList());
    }

    /**
     * 获取单个模型配置详情
     *
     * @param id 配置 ID
     * @return RestfulResult<ModelConfigVO>
     */
    @GetMapping("/{id}")
    public RestfulResult getModelConfig(@PathVariable("id") Long id) {
        return RestfulResult.success(modelConfigService.getModelConfig(id));
    }

    /**
     * 创建新的模型配置
     *
     * @param dto 创建请求体
     * @return RestfulResult<Long> 返回新创建的配置 ID
     */
    @PostMapping("/create")
    public RestfulResult createModelConfig(@RequestBody ModelConfigDTO dto) {
        return RestfulResult.success(modelConfigService.createModelConfig(dto));
    }

    /**
     * 更新模型配置
     *
     * @param id  配置 ID
     * @param dto 更新请求体
     * @return RestfulResult
     */
    @PutMapping("/update/{id}")
    public RestfulResult updateModelConfig(@PathVariable("id") Long id, @RequestBody ModelConfigDTO dto) {
        modelConfigService.updateModelConfig(id, dto);
        return RestfulResult.success();
    }

    /**
     * 删除模型配置
     *
     * @param id 配置 ID
     * @return RestfulResult
     */
    @DeleteMapping("/delete/{id}")
    public RestfulResult deleteModelConfig(@PathVariable("id") Long id) {
        modelConfigService.deleteModelConfig(id);
        return RestfulResult.success();
    }


}
