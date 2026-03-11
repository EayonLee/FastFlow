package com.fastflow.entity.invite;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class CreateInviteCodeDTO {

    /**
     * 需要生成的邀请码数量。
     */
    @NotNull(message = "生成数量不能为空")
    @Min(value = 1, message = "生成数量不能小于1")
    @Max(value = 1000, message = "单次最多生成1000个邀请码")
    private Integer count;
}
