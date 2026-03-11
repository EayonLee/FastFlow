package com.fastflow.entity.invite;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("invite_codes")
public class InviteCode {

    /**
     * 邀请码（6位字母数字），主键。
     */
    @TableId(value = "invite_code", type = IdType.INPUT)
    private String inviteCode;

    /**
     * 是否已使用：false-未使用，true-已使用。
     */
    @TableField("is_used")
    private Boolean isUsed;

    /**
     * 使用人 UID。
     */
    @TableField("used_by_uid")
    private Long usedByUid;

    /**
     * 使用时间。
     */
    @TableField("used_at")
    private LocalDateTime usedAt;

    /**
     * 创建时间。
     */
    @TableField(value = "created_at")
    private LocalDateTime createdAt;
}
