package com.fastflow.entity.auth;

import com.fastflow.entity.user.UserInfo;
import lombok.Builder;
import lombok.Data;
import lombok.experimental.Accessors;

@Data
@Builder
@Accessors(chain = true)
public class LoginVO {
    private String token;
    private UserInfo userInfo;
}
