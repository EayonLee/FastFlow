package com.fastflow.service.invite;

import cn.hutool.core.util.RandomUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fastflow.common.exception.BizInviteCodeException;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.common.exception.ErrorCode;
import com.fastflow.entity.invite.CreateInviteCodeVO;
import com.fastflow.entity.invite.InviteCode;
import com.fastflow.mapper.InviteCodeMapper;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 邀请码服务：
 * 1. 按指定数量生成邀请码并入库；
 * 2. 按条件查询邀请码列表；
 * 3. 校验邀请码是否可用；
 * 4. 原子地将邀请码标记为已使用。
 */
@Service
public class InviteCodeService extends ServiceImpl<InviteCodeMapper, InviteCode> {

    private static final String INVITE_CODE_REGEX = "^[A-Za-z0-9]{6}$";

    /**
     * 允许创建邀请码的固定邮箱。
     */
    private static final String INVITE_CODE_ADMIN_EMAIL = "lizhengtai@360.cn";

    /**
     * 邀请码字符集（数字 + 大小写字母）。
     */
    private static final String CODE_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

    /**
     * 邀请码固定长度。
     */
    private static final int CODE_LENGTH = 6;

    /**
     * 单次最大生成数量（服务层兜底限制）。
     */
    private static final int MAX_CREATE_COUNT = 1000;

    /**
     * 查询邀请码列表。
     * 过滤条件均为“精确匹配”，并按 created_at 倒序返回。
     *
     * @param inviteCode 邀请码（可选）
     * @param isUsed 是否已使用（可选）
     * @param usedByUid 使用人 UID（可选）
     * @return 邀请码列表
     */
    public List<InviteCode> listInviteCodes(String inviteCode, Boolean isUsed, Long usedByUid) {
        LambdaQueryWrapper<InviteCode> queryWrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(inviteCode)) {
            queryWrapper.eq(InviteCode::getInviteCode, normalizeInviteCode(inviteCode));
        }
        if (isUsed != null) {
            queryWrapper.eq(InviteCode::getIsUsed, isUsed);
        }
        if (usedByUid != null) {
            queryWrapper.eq(InviteCode::getUsedByUid, usedByUid);
        }

        queryWrapper.orderByDesc(InviteCode::getCreatedAt);
        return this.list(queryWrapper);
    }

    /**
     * 创建指定数量的邀请码。
     *
     * @param count 需要生成的邀请码数量
     * @param operatorEmail 操作人邮箱（用于权限校验）
     * @return 生成结果（请求数量、成功数量、邀请码列表）
     */
    @Transactional(rollbackFor = Exception.class)
    public CreateInviteCodeVO createInviteCodes(Integer count, String operatorEmail) {
        // 仅固定邮箱允许创建邀请码。
        if (!INVITE_CODE_ADMIN_EMAIL.equals(operatorEmail)) {
            throw new BusinessException(ErrorCode.FORBIDDEN.getCode(), "无权限创建邀请码");
        }
        if (count == null || count <= 0) {
            throw new BusinessException(ErrorCode.PARAM_ERROR.getCode(), "生成数量必须大于0");
        }
        if (count > MAX_CREATE_COUNT) {
            throw new BusinessException(ErrorCode.PARAM_ERROR.getCode(), "单次最多生成1000个邀请码");
        }

        // 限制最大尝试次数，防止极端情况下无限循环。
        int maxAttempts = Math.max(count * 30, 100);
        int attempts = 0;
        List<String> createdCodes = new ArrayList<>(count);

        while (createdCodes.size() < count && attempts < maxAttempts) {
            attempts++;
            String inviteCode = RandomUtil.randomString(CODE_CHARSET, CODE_LENGTH);

            InviteCode entity = new InviteCode();
            entity.setInviteCode(inviteCode);
            entity.setIsUsed(false);

            try {
                // 依赖数据库主键唯一约束做最终防重。
                boolean saved = this.save(entity);
                if (saved) {
                    createdCodes.add(inviteCode);
                }
            } catch (DuplicateKeyException ignored) {
                // 命中唯一键冲突时继续重试生成
            }
        }

        if (createdCodes.size() < count) {
            throw new BusinessException(ErrorCode.SYSTEM_ERROR.getCode(), "邀请码生成失败，请重试");
        }

        return CreateInviteCodeVO.builder()
                .requestedCount(count)
                .generatedCount(createdCodes.size())
                .inviteCodes(createdCodes)
                .build();
    }

    /**
     * 规范化邀请码输入，并严格区分为空与格式错误。
     *
     * @param inviteCode 原始邀请码
     * @return 去除首尾空白后的邀请码
     */
    private String normalizeInviteCode(String inviteCode) {
        if (!StringUtils.hasText(inviteCode)) {
            throw BizInviteCodeException.empty();
        }
        String normalizedInviteCode = inviteCode.trim();
        if (!normalizedInviteCode.matches(INVITE_CODE_REGEX)) {
            throw BizInviteCodeException.formatError();
        }
        return normalizedInviteCode;
    }

    /**
     * 校验邀请码是否存在且可用。
     *
     * @param inviteCode 邀请码
     */
    public void validateInviteCode(String inviteCode) {
        String normalizedInviteCode = normalizeInviteCode(inviteCode);
        InviteCode codeEntity = this.getById(normalizedInviteCode);
        if (codeEntity == null) {
            throw BizInviteCodeException.notFound();
        }
        if (Boolean.TRUE.equals(codeEntity.getIsUsed())) {
            throw BizInviteCodeException.used();
        }
    }

    /**
     * 原子地将邀请码标记为已使用。
     * 说明：
     * 1. 仅当邀请码当前状态为未使用时更新成功；
     * 2. 该方法可安全应对并发注册争抢同一个邀请码；
     * 3. 建议在外层事务中调用，便于与用户注册一起提交/回滚。
     *
     * @param inviteCode 邀请码
     * @param uid 使用人 UID
     */
    @Transactional(rollbackFor = Exception.class, propagation = Propagation.MANDATORY)
    public void consumeInviteCode(String inviteCode, Long uid) {
        String normalizedInviteCode = normalizeInviteCode(inviteCode);
        LocalDateTime now = LocalDateTime.now();
        boolean updated = this.lambdaUpdate()
                .set(InviteCode::getIsUsed, true)
                .set(InviteCode::getUsedByUid, uid)
                .set(InviteCode::getUsedAt, now)
                .eq(InviteCode::getInviteCode, normalizedInviteCode)
                .eq(InviteCode::getIsUsed, false)
                .update();

        if (!updated) {
            InviteCode codeEntity = this.getById(normalizedInviteCode);
            if (codeEntity == null) {
                throw BizInviteCodeException.notFound();
            }
            if (Boolean.TRUE.equals(codeEntity.getIsUsed())) {
                throw BizInviteCodeException.used();
            }
            throw new BusinessException(ErrorCode.SYSTEM_ERROR.getCode(), "邀请码状态异常，请稍后重试");
        }
    }
}
