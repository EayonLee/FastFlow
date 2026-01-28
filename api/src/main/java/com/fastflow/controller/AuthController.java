package com.fastflow.controller;

import com.fastflow.common.result.RestfulResult;
import com.fastflow.entity.auth.LoginDTO;
import com.fastflow.entity.auth.RegisterDTO;
import com.fastflow.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;


/**
 * 用户认证接口控制器
 * 
 * 主要功能：
 * 1. 处理用户登录请求，返回 JWT Token
 * 2. 处理用户注册请求
 * 3. 统一处理参数校验和业务异常
 */
@RestController
@RequestMapping("/fastflow/api/v1/auth")
public class AuthController {

    @Autowired
    private AuthService authService;

    /**
     * 用户登录接口
     * <p>
     * 接收用户登录信息，调用Service层进行业务处理。
     * 如果登录成功，返回包含JWT token的登录成功VO；
     * 如果登录失败（如用户名或密码错误），将抛出 BusinessException 异常，
     * 由 GlobalExceptionHandler 全局异常处理器捕获并返回标准错误响应。
     *
     * @param request 登录信息DTO，包含用户名、密码等，并进行参数校验
     * @return 登录成功后的用户信息VO，包含JWT token
     */
    @PostMapping("/login")
    public RestfulResult login(@RequestBody @Valid LoginDTO request) {
        return RestfulResult.success(authService.login(request));
    }

    /**
     * 用户注册接口
     * <p>
     * 接收用户注册信息，调用Service层进行业务处理。
     * 如果Service层抛出 BusinessException (如用户名已存在)，
     * 将由 GlobalExceptionHandler 全局异常处理器自动捕获并返回标准错误响应。
     *
     * @param request 注册信息DTO，包含用户名、密码、邮箱等，并进行参数校验
     * @return 注册成功后的用户信息VO
     */
    @PostMapping("/register")
    public RestfulResult register(@RequestBody @Valid RegisterDTO request) {
        return RestfulResult.success(authService.register(request));
    }


    /**
     * 校验登录Token接口
     * <p>
     * 接收登录Token，调用Service层进行校验。
     * 如果Token有效，返回包含用户信息的Map；
     * 如果Token无效（如过期、格式错误），将抛出 BusinessException 异常，
     * 由 GlobalExceptionHandler 全局异常处理器捕获并返回标准错误响应。
     *
     * @param token 登录Token，从请求头的 Authorization 字段中获取
     * @return 包含用户信息的Map，包含uid, username, email
     */
    @PostMapping("/checkLogin")
    public RestfulResult checkLogin(@RequestHeader("Authorization") String token) {
        return RestfulResult.success(authService.checkLogin(token));
    }
}
