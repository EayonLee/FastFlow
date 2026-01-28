package com.fastflow.entity.auth;

import lombok.Data;
import lombok.experimental.Accessors;

import java.time.LocalDateTime;

@Data
@Accessors(chain = true)
public class RegisterVO {
    private Long uid;
    private String username;
    private String email;
    private Integer status;
    private LocalDateTime createdAt;
}
