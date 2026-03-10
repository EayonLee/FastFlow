package com.fastflow.controller.slash;

import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.result.RestfulResult;
import com.fastflow.service.slash.SlashService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Slash 目录代理控制器。
 *
 * 设计目的：
 * 1) 前端统一访问 API 模块，不直接访问 Nexus 服务；
 * 2) API 模块负责透传登录态并代理请求；
 * 3) 对前端统一输出 RestfulResult 结构（code/message/data）。
 */
@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/clash")
public class SlashController {

    @Autowired
    private SlashService slashService;

    /**
     * 获取 Slash 目录（skills + mcp 占位）。
     *
     * 调用链路：
     * 前端 -> API(`/fastflow/api/v1/clash/catalog`) -> Nexus(`/fastflow/nexus/v1/slash/catalog`)
     *
     * @param token 用户登录态令牌，来自请求头 Authorization
     * @return 统一响应结构，data 内包含 skills/mcp
     */
    @GetMapping("/catalog")
    public RestfulResult getCatalog(@RequestHeader("Authorization") String token) {
        return RestfulResult.success(slashService.getCatalog(token));
    }
}
