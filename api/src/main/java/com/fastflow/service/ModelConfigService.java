package com.fastflow.service;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.entity.model.ModelConfig;
import com.fastflow.entity.model.ModelConfigDTO;
import com.fastflow.entity.model.ModelConfigVO;
import com.fastflow.mapper.ModelConfigMapper;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 模型配置业务逻辑实现类
 * 主要功能：
 * 1. 提供模型配置的增删改查功能
 * 2. 校验模型名称唯一性
 */
@Service
public class ModelConfigService extends ServiceImpl<ModelConfigMapper, ModelConfig> {

    /**
     * 创建模型配置
     *
     * @param dto 前端传入的配置参数
     * @return 新创建的配置ID
     */
    public Long createModelConfig(ModelConfigDTO dto) {
        // 1. 校验模型名称是否已存在
        long count = this.count(new LambdaQueryWrapper<ModelConfig>()
                .eq(ModelConfig::getModelName, dto.getModelName()));
        if (count > 0) {
            throw new BusinessException("模型名称已存在，请更换名称");
        }

        // 2. 转换为实体对象并保存
        ModelConfig modelConfig = BeanUtil.copyProperties(dto, ModelConfig.class);
        if (modelConfig.getSortOrder() == null) {
            modelConfig.setSortOrder(getNextSortOrder());
        }
        this.save(modelConfig);

        return modelConfig.getId();
    }

    /**
     * 更新模型配置
     *
     * @param id  配置ID
     * @param dto 更新参数
     */
    public void updateModelConfig(Long id, ModelConfigDTO dto) {
        // 1. 检查是否存在
        ModelConfig existingConfig = this.getById(id);
        if (existingConfig == null) {
            throw new BusinessException("模型配置不存在");
        }

        // 2. 如果修改了名称，需要校验唯一性（排除自己）
        if (!existingConfig.getModelName().equals(dto.getModelName())) {
            long count = this.count(new LambdaQueryWrapper<ModelConfig>()
                    .eq(ModelConfig::getModelName, dto.getModelName())
                    .ne(ModelConfig::getId, id));
            if (count > 0) {
                throw new BusinessException("模型名称已存在，请更换名称");
            }
        }

        // 3. 更新属性
        Integer currentSortOrder = existingConfig.getSortOrder();
        BeanUtil.copyProperties(dto, existingConfig);
        existingConfig.setId(id);
        existingConfig.setSortOrder(currentSortOrder);

        this.updateById(existingConfig);
    }

    /**
     * 获取模型配置详情
     *
     * @param id 配置ID
     * @return VO对象
     */
    public ModelConfigVO getModelConfig(Long id) {
        ModelConfig modelConfig = this.getById(id);
        if (modelConfig == null) {
            throw new BusinessException("模型配置不存在");
        }
        return BeanUtil.copyProperties(modelConfig, ModelConfigVO.class);
    }

    /**
     * 获取模型ApiKey
     *
     * @param id 配置ID
     * @return
     */
    public String getModelApiKey(Long id) {
        ModelConfig modelConfig = this.getById(id);
        if (modelConfig == null) {
            throw new BusinessException("模型配置不存在");
        }
        return modelConfig.getApiKey();
    }

    /**
     * 获取所有模型配置列表
     *
     * @return List<ModelConfigVO>
     */
    public List<ModelConfigVO> getModelConfigList() {
        List<ModelConfig> list = this.list(new LambdaQueryWrapper<ModelConfig>()
                .orderByAsc(ModelConfig::getSortOrder));

        return list.stream()
                .map(item -> BeanUtil.copyProperties(item, ModelConfigVO.class))
                .collect(Collectors.toList());
    }

    /**
     * 获取下一个排序值（最大值 + 1）
     */
    private Integer getNextSortOrder() {
        Integer max = this.lambdaQuery()
                .select(ModelConfig::getSortOrder)
                .orderByDesc(ModelConfig::getSortOrder)
                .last("LIMIT 1")
                .oneOpt()
                .map(ModelConfig::getSortOrder)
                .orElse(null);
        return max == null ? 0 : max + 1;
    }

    /**
     * 删除模型配置
     *
     * @param id 配置ID
     */
    public void deleteModelConfig(Long id) {
        boolean removed = this.removeById(id);
        if (!removed) {
            throw new BusinessException("删除失败，配置可能不存在");
        }
    }

}
