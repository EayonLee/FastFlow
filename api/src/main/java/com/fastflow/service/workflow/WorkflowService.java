package com.fastflow.service.workflow;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.IdUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.entity.user.UserInfo;
import com.fastflow.entity.workflow.Workflow;
import com.fastflow.entity.workflow.WorkflowDTO;
import com.fastflow.entity.workflow.WorkflowVO;
import com.fastflow.mapper.WorkflowMapper;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 工作流业务逻辑实现类
 * <p>
 * 主要功能：
 * 1. 实现了工作流的增删改查（CRUD）操作
 * 2. 处理工作流的所有权校验（确保用户只能操作自己的工作流）
 * 3. 负责 ID 生成（使用 24 位 ObjectId）和数据转换（Entity -> VO）
 * <p>
 * 注意事项：
 * - 所有涉及到 ID 的操作，现在都统一使用 String 类型（24位 ObjectId）
 * - 在获取列表时，为了性能考虑，故意过滤掉了 `config` 大字段
 * - 涉及到修改和删除的操作，必须严格校验 `uid`，防止越权操作
 */
@Service
public class WorkflowService extends ServiceImpl<WorkflowMapper, Workflow> {


    /**
     * 根据 ID 获取单个工作流详情
     *
     * @param userInfo 当前登录用户信息
     * @param id       工作流 ID
     * @return WorkflowVO 包含完整信息（含 config）
     */
    public WorkflowVO getWorkflow(UserInfo userInfo, String id) {
        // 1. 查询数据库，同时校验 ID 和 创建者 UID，确保只能查到自己的
        Workflow workflow = this.getOne(new LambdaQueryWrapper<Workflow>()
                .eq(Workflow::getId, id)
                .eq(Workflow::getCreator, userInfo.getUid()));

        // 如果没查到，说明不存在或者不属于该用户，直接抛出业务异常
        if (workflow == null) {
            throw new BusinessException("工作流不存在或无权访问");
        }

        // 3. 将实体对象转换为 VO 对象返给前端
        WorkflowVO vo = BeanUtil.copyProperties(workflow, WorkflowVO.class);
        // 创建者昵称
        vo.setCreatorName(userInfo.getUsername());

        return vo;
    }


    /**
     * 获取当前用户的所有工作流列表
     *
     * @param userInfo 当前登录用户信息
     * @return List<WorkflowVO> 工作流列表（不含 config 详情）
     */
    public List<WorkflowVO> getWorkflowList(UserInfo userInfo) {
        // 1. 查询该用户创建的所有工作流
        // 注意：这里使用了 select 指定字段，特意排除了 `config` 字段
        // 因为 config 存的是巨大的 JSON 字符串，列表页根本不需要，查出来浪费带宽和内存
        List<Workflow> workflows = this.list(new LambdaQueryWrapper<Workflow>()
                .select(Workflow::getId, Workflow::getName, Workflow::getDescription, Workflow::getCreator, Workflow::getCreatedAt, Workflow::getUpdatedAt)
                .eq(Workflow::getCreator, userInfo.getUid())
                .orderByDesc(Workflow::getUpdatedAt)); // 按更新时间倒序，最近修改的排前面

        // 2. 使用 Stream 流将 Entity 列表批量转换为 VO 列表
        return workflows.stream()
                .map(workflow -> {
                    // 属性拷贝
                    WorkflowVO vo = BeanUtil.copyProperties(workflow, WorkflowVO.class);
                    // 填充统一查询到的昵称
                    vo.setCreatorName(userInfo.getUsername());
                    return vo;
                })
                .collect(Collectors.toList());
    }


    /**
     * 创建一个新的工作流
     *
     * @param userInfo 当前登录用户信息
     * @param workflow 前端传来的 DTO 对象
     * @return 创建成功后的工作流 ID
     */
    public String createWorkflow(UserInfo userInfo, WorkflowDTO workflow) {
        // 构建数据库实体对象
        Workflow entity = Workflow.builder()
                // 生成 ID：使用 Hutool 的 ObjectId 生成器，生成 24 位 MongoDB 风格的 ID
                // 这种 ID 有序且唯一，比 UUID 短，适合做 URL 参数
                .id(IdUtil.objectId())
                .name(workflow.getName())
                .description(workflow.getDescription())
                .config(workflow.getConfig()) // 初始配置
                .creator(userInfo.getUid()) // 绑定创建者
                .build();

        // 保存到数据库
        this.save(entity);

        // 返回 ID 方便前端跳转
        return entity.getId();
    }

    /**
     * 更新工作流信息
     *
     * @param userInfo   当前登录用户信息
     * @param workflowId 要更新的工作流 ID
     * @param workflow   前端传来的更新数据
     */
    public void updateWorkflow(UserInfo userInfo, String workflowId, WorkflowDTO workflow) {
        // 1. 安全检查：必须确保工作流存在，并且是当前用户创建的
        Workflow exists = this.getOne(new LambdaQueryWrapper<Workflow>()
                .eq(Workflow::getId, workflowId)
                .eq(Workflow::getCreator, userInfo.getUid()));

        // 如果校验失败，直接抛异常阻止后续操作
        if (exists == null) {
            throw new BusinessException("工作流不存在或无权修改");
        }

        // 2. 构建更新实体，只更新允许修改的字段
        Workflow updateEntity = Workflow.builder()
                .id(workflowId) // 主键必须有
                .name(workflow.getName())
                .description(workflow.getDescription())
                .config(workflow.getConfig()) // 核心配置更新
                .build();

        // 执行更新操作
        this.updateById(updateEntity);
    }

    /**
     * 删除工作流
     *
     * @param userInfo 当前登录用户信息
     * @param id       工作流 ID
     */
    public void deleteWorkflow(UserInfo userInfo, String id) {
        // 1. 安全检查：同样要确保工作流存在且属于当前用户
        Workflow exists = this.getOne(new LambdaQueryWrapper<Workflow>()
                .eq(Workflow::getId, id)
                .eq(Workflow::getCreator, userInfo.getUid()));

        // 越权或者不存在，抛异常
        if (exists == null) {
            throw new BusinessException("工作流不存在或无权删除");
        }

        // 2. 校验通过，执行物理删除
        this.removeById(id);
    }


}
