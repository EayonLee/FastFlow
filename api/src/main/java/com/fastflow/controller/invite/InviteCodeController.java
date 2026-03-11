package com.fastflow.controller.invite;

import com.fastflow.common.annotation.LoginCheck;
import com.fastflow.common.result.RestfulResult;
import com.fastflow.entity.invite.CreateInviteCodeDTO;
import com.fastflow.entity.user.UserInfo;
import com.fastflow.service.invite.InviteCodeService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 邀请码管理接口。
 * 提供批量生成与列表查询能力。
 */
@LoginCheck
@RestController
@RequestMapping("/fastflow/api/v1/inviteCode")
public class InviteCodeController {

    @Autowired
    private InviteCodeService inviteCodeService;

    /**
     * 批量生成邀请码。
     *
     * @param userInfo 当前登录用户信息（从登录拦截器注入）
     * @param request 包含 count（生成数量）
     * @return 生成结果
     */
    @PostMapping("/create")
    public RestfulResult createInviteCodes(@RequestAttribute("userInfo") UserInfo userInfo,
                                           @RequestBody @Valid CreateInviteCodeDTO request) {
        return RestfulResult.success(inviteCodeService.createInviteCodes(request.getCount(), userInfo.getEmail()));
    }

    /**
     * 邀请码列表查询。
     * 支持按邀请码、是否使用、使用人 UID 精确过滤，并按创建时间倒序返回。
     *
     * @param inviteCode 邀请码（精确匹配）
     * @param isUsed 是否已使用（精确匹配）
     * @param usedByUid 使用人 UID（精确匹配）
     * @return 邀请码列表
     */
    @GetMapping("/list")
    public RestfulResult listInviteCodes(@RequestParam(value = "invite_code", required = false) String inviteCode,
                                         @RequestParam(value = "is_used", required = false) Boolean isUsed,
                                         @RequestParam(value = "used_by_uid", required = false) Long usedByUid) {
        return RestfulResult.success(inviteCodeService.listInviteCodes(inviteCode, isUsed, usedByUid));
    }
}
