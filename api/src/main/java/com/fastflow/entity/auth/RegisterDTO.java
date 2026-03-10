package com.fastflow.entity.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

@Data
public class RegisterDTO {

    @NotBlank(message = "用户名不能为空")
    @Pattern(regexp = "^[A-Za-z0-9\\u4e00-\\u9fa5]{5,12}$", message = "用户名仅支持中英文和数字，长度为5-12位")
    private String username;

    @NotBlank(message = "密码不能为空")
    private String password;

    @NotBlank(message = "邮箱不能为空")
    @Pattern(regexp = "^[a-zA-Z0-9._%+-]+@360\\.cn$", message = "邮箱格式不正确，且必须是 @360.cn 邮箱")
    private String email;

    @NotBlank(message = "邀请码不能为空")
    @Pattern(regexp = "^[A-Za-z0-9]{6}$", message = "邀请码必须是6位字母或数字")
    private String inviteCode;
}
