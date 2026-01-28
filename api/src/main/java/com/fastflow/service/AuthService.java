package com.fastflow.service;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.RandomUtil;
import cn.hutool.crypto.digest.BCrypt;
import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.common.exception.ErrorCode;
import com.fastflow.entity.user.User;
import com.fastflow.entity.auth.LoginDTO;
import com.fastflow.entity.auth.LoginVO;
import com.fastflow.entity.auth.RegisterDTO;
import com.fastflow.entity.auth.RegisterVO;
import com.fastflow.entity.user.UserInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

import cn.hutool.core.util.ReUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.crypto.SecureUtil;
import cn.hutool.crypto.symmetric.AES;


/**
 * 用户认证业务逻辑实现类
 * <p>
 * 主要功能：
 * 1. 用户登录校验（解密密码、验证BCrypt、生成JWT）
 * 2. 用户注册逻辑（唯一性校验、密码强度校验、密码加密、UID生成）
 * 3. 密码解密工具方法
 */
@Slf4j
@Service
public class AuthService {

    @Autowired
    private UserService userService;

    @Value("${auth.jwt.secret}")
    private String jwtSecret;

    @Value("${auth.jwt.expiration}")
    private long jwtExpiration;

    @Value("${auth.password.secret-key}")
    private String aesKey;

    /**
     * 解密密码
     */
    private String decryptPassword(String encryptedPassword) {
        try {
            if (StrUtil.isBlank(encryptedPassword)) {
                return encryptedPassword;
            }
            // 构建AES
            AES aes = SecureUtil.aes(aesKey.getBytes(StandardCharsets.UTF_8));
            return aes.decryptStr(encryptedPassword);
        } catch (Exception e) {
            log.error("密码解密失败", e);
            throw new BusinessException(ErrorCode.PARAM_ERROR.getCode(), "密码解密失败，请检查加密方式");
        }
    }

    @Transactional(rollbackFor = Exception.class)
    /**
     * 用户登录业务处理
     *
     * @param request 登录请求参数 (email, password)
     * @return LoginVO 包含 Token 和用户基本信息
     */
    public LoginVO login(LoginDTO request) {
        // 0. 解密密码
        String realPassword = decryptPassword(request.getPassword());

        // 1. 查询用户
        User user = userService.getOne(new LambdaQueryWrapper<User>()
                .eq(User::getEmail, request.getEmail()));

        if (user == null) {
            throw new BusinessException(ErrorCode.USER_PASSWORD_ERROR);
        }

        // 2. 校验密码
        if (!BCrypt.checkpw(realPassword, user.getPassword())) {
            throw new BusinessException(ErrorCode.USER_PASSWORD_ERROR);
        }

        // 3. 校验状态
        if (user.getStatus() != 1) {
            throw new BusinessException(ErrorCode.USER_ACCOUNT_LOCKED);
        }

        // 4. 生成Token
        Map<String, Object> payload = new HashMap<>();
        payload.put("uid", user.getUid());
        payload.put("email", user.getEmail());
        payload.put("expire_time", System.currentTimeMillis() + jwtExpiration * 1000);

        String token = JWTUtil.createToken(payload, jwtSecret.getBytes(StandardCharsets.UTF_8));

        // 5. 组装返回
        LoginVO loginVO = LoginVO.builder()
                .token(token)
                .userInfo(BeanUtil.copyProperties(user, UserInfo.class))
                .build();

        log.info("用户登录成功，uid={}, username={}, email={}", user.getUid(), user.getUsername(), user.getEmail());
        return loginVO;
    }

    @Transactional(rollbackFor = Exception.class)
    /**
     * 用户注册业务处理
     *
     * @param request 注册请求参数 (username, email, password)
     * @return RegisterVO 注册成功后的用户信息
     */
    public RegisterVO register(RegisterDTO request) {
        log.info("开始处理用户注册请求: username={}, email={}", request.getUsername(), request.getEmail());

        // 1. 检查用户名是否存在
        long count = userService.count(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, request.getUsername()));
        if (count > 0) {
            log.warn("注册失败，用户名已存在: {}", request.getUsername());
            throw new BusinessException(ErrorCode.USER_NAME_ALREADY_EXISTS);
        }

        // 2. 检查邮箱是否存在
        long emailCount = userService.count(new LambdaQueryWrapper<User>()
                .eq(User::getEmail, request.getEmail()));
        if (emailCount > 0) {
            log.warn("注册失败，邮箱已存在: {}", request.getEmail());
            throw new BusinessException(ErrorCode.USER_EMAIL_ALREADY_EXISTS);
        }

        // 3. 创建用户
        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());

        // 4. 解密并校验密码强度
        String realPassword = decryptPassword(request.getPassword());
        if (!ReUtil.isMatch("^(?=.*[a-zA-Z])(?=.*\\d).+$", realPassword)) {
            throw new BusinessException(ErrorCode.PARAM_ERROR.getCode(), "密码必须包含字母和数字");
        }

        // 5. 密码加密存储
        user.setPassword(BCrypt.hashpw(realPassword));
        user.setStatus(1); // 1-正常

        // 6. 保存用户（解决并发UID重复问题）
        int maxRetries = 5;
        for (int i = 0; i < maxRetries; i++) {
            try {
                // 生成9位随机数字UID (100000000 - 999999999)
                user.setUid(RandomUtil.randomLong(100000000, 999999999));
                userService.save(user);
                break;
            } catch (DuplicateKeyException e) {
                // 如果是最后一次重试，仍然失败，则抛出异常
                if (i == maxRetries - 1) {
                    log.error("用户注册生成UID重试失败: username={}", request.getUsername(), e);
                    throw new BusinessException(ErrorCode.SYSTEM_ERROR);
                }
                log.warn("UID生成冲突，正在重试: username={}, uid={}", request.getUsername(), user.getUid());
            }
        }

        log.info("用户注册成功: uid={}, username={}", user.getUid(), user.getUsername());

        // 6. 返回VO
        return BeanUtil.copyProperties(user, RegisterVO.class);
    }

    /**
     * 校验登录Token
     *
     * @param token 登录Token
     * @return LoginVO 包含Token和用户信息
     */
    public UserInfo checkLogin(String token) {
        if (StrUtil.isBlank(token)) {
            throw new BusinessException(ErrorCode.NOT_LOGIN);
        }

        // 去除 Bearer 前缀
        if (token.startsWith("Bearer ")) {
            token = token.substring(7);
        }

        try {
            // 5. 校验签名
            if (!JWTUtil.verify(token, jwtSecret.getBytes(StandardCharsets.UTF_8))) {
                throw new BusinessException(ErrorCode.NOT_LOGIN);
            }

            // 6. 校验过期
            Object expireTimeObj = JWTUtil.parseToken(token).getPayload("expire_time");
            if (expireTimeObj != null) {
                long expireTime = Long.parseLong(expireTimeObj.toString());
                if (System.currentTimeMillis() > expireTime) {
                    throw new BusinessException(ErrorCode.NOT_LOGIN);
                }
            }

        } catch (Exception e) {
            log.error("Token校验失败: {}", e.getMessage());
            throw new BusinessException(ErrorCode.NOT_LOGIN);
        }


        // 7. 解析Token，获取用户ID
        JWT jwt = JWTUtil.parseToken(token);
        Long uid = Long.parseLong(jwt.getPayload("uid").toString());

        // 查询用户信息
        User user = userService.getById(uid);
        if (user == null) {
            throw new BusinessException(ErrorCode.NOT_LOGIN);
        }

        log.debug("Token校验成功: uid={}, username={}, email={}", user.getUid(), user.getUsername(), user.getEmail());
        // 8. 校验通过，返回用户信息
        return UserInfo.builder()
                .uid(user.getUid())
                .username(user.getUsername())
                .email(user.getEmail())
                .status(user.getStatus())
                .createdAt(user.getCreatedAt())
                .updatedAt(user.getUpdatedAt())
                .build();
    }
}
