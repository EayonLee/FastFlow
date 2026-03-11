package com.fastflow.entity.invite;

import lombok.Builder;
import lombok.Data;

import java.util.List;

@Data
@Builder
public class CreateInviteCodeVO {

    /**
     * 请求生成数量。
     */
    private Integer requestedCount;

    /**
     * 实际生成成功数量。
     */
    private Integer generatedCount;

    /**
     * 生成的邀请码列表。
     */
    private List<String> inviteCodes;
}
