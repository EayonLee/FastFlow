package com.fastflow.common.annotation;

import java.lang.annotation.*;

/**
 * 登录校验注解
 * 可添加在类或方法上
 */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface LoginCheck {
    /**
     * 是否必须登录
     */
    boolean required() default true;
}
