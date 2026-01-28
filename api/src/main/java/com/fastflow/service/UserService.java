package com.fastflow.service;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.common.exception.ErrorCode;
import com.fastflow.entity.user.User;
import com.fastflow.entity.user.UserInfo;
import com.fastflow.mapper.UserMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;


/**
 * 用户管理业务逻辑实现类
 * 
 * 主要功能：
 * 1. 提供用户信息的查询功能
 * 2. 继承 MyBatis-Plus ServiceImpl 提供基础 CRUD 能力
 */
@Slf4j
@Service
public class UserService extends ServiceImpl<UserMapper, User> {


    /**
     * 获取用户信息
     * 
     * @param uid 用户UID
     * @return UserVo
     */
    public UserInfo getUserInfo(Long uid) {
        User user = this.getOne(new LambdaQueryWrapper<User>().eq(User::getUid, uid));
        log.debug("获取用户信息，用户UID：{}, 用户信息：{}", uid, user);
        if (user == null) {
            log.warn("用户不存在，用户UID：{}", uid);
            throw new BusinessException(ErrorCode.USER_NOT_FOUND);
        }
        return BeanUtil.copyProperties(user, UserInfo.class);
    }
}
