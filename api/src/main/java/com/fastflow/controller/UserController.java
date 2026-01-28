package com.fastflow.controller;

import com.fastflow.common.result.RestfulResult;
import com.fastflow.entity.user.UserInfo;
import com.fastflow.service.UserService;
import com.fastflow.common.annotation.LoginCheck;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;



/**
 * 用户信息接口控制器
 * 
 * 主要功能：
 * 1. 获取当前登录用户的个人信息
 * 2. 依赖 @LoginCheck 注解进行统一鉴权
 */
@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/user")
public class UserController {

    @Autowired
    private UserService userService;

    /**
     * 获取用户信息
     * 
     * @param userInfo 当前登录用户信息
     * @return RestfulResult<UserVO> 用户详细信息
     */
    @GetMapping("/info")
    public RestfulResult getUserInfo(@RequestAttribute("userInfo") UserInfo userInfo) {
        return RestfulResult.success(userService.getUserInfo(userInfo.getUid()));
    }
}
