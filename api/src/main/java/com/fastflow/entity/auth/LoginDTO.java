package com.fastflow.entity.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

@Data
public class LoginDTO {

    @NotBlank(message = "邮箱不能为空")
    @Pattern(regexp = "^[a-zA-Z0-9._%+-]+@360\\.cn$", message = "邮箱格式不正确，且必须是 @360.cn 邮箱")
    private String email;

    @NotBlank(message = "密码不能为空")
    private String password;
}
