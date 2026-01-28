package com.fastflow.common.interceptor;

import cn.hutool.core.util.StrUtil;
import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.common.exception.ErrorCode;
import com.fastflow.entity.user.UserInfo;
import com.fastflow.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import java.lang.reflect.Method;

/**
 * 登录拦截器
 * 用于替代 LoginAspect，解决 @RequestAttribute 在 Aspect 之后执行导致无法获取 userInfo 的问题
 */
@Component
public class LoginInterceptor implements HandlerInterceptor {

    @Autowired
    private AuthService authService;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        // 1. 如果不是映射到方法直接通过 (例如静态资源)
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }

        HandlerMethod handlerMethod = (HandlerMethod) handler;
        Method method = handlerMethod.getMethod();

        // 2. 获取 LoginCheck 注解
        // 优先获取方法上的注解
        LoginCheck loginCheck = method.getAnnotation(LoginCheck.class);
        // 如果方法上没有，尝试获取类上的
        if (loginCheck == null) {
            loginCheck = method.getDeclaringClass().getAnnotation(LoginCheck.class);
        }

        // 3. 判断是否需要校验
        // 如果没有注解，或者 required=false，则直接放行
        if (loginCheck == null || !loginCheck.required()) {
            return true;
        }

        // 4. 获取Token
        String token = request.getHeader("Authorization");
        if (StrUtil.isBlank(token)) {
            throw new BusinessException(ErrorCode.NOT_LOGIN);
        }

        // 5. 校验Token
        UserInfo userInfo = authService.checkLogin(token);

        // 6. 校验通过，将用户信息放入请求属性，方便后续 @RequestAttribute 获取
        request.setAttribute("userInfo", userInfo);

        return true;
    }
}
