package com.fastflow.service.user;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.util.RandomUtil;
import cn.hutool.crypto.digest.BCrypt;
import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fastflow.common.exception.BusinessException;
import com.fastflow.common.exception.ErrorCode;
import com.fastflow.service.invite.InviteCodeService;
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
    /**
     * 注册密码规则：
     * 仅允许大小写字母、数字和 _-@!#$%&*，长度 6~22。
     */
    private static final String PASSWORD_REGEX = "^[A-Za-z0-9_@!#$%&*\\-]{6,22}$";

    @Autowired
    private UserService userService;

    @Autowired
    private InviteCodeService inviteCodeService;

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
            throw new BusinessException(
                    ErrorCode.PARAM_ERROR.getCode(),
                    "密码解密失败，请检查加密方式",
                    Map.of("password", "密码格式错误，请重试")
            );
        }
    }

    private void validateDecryptedPassword(String password) {
        if (StrUtil.isBlank(password)) {
            throw new BusinessException(
                    ErrorCode.PARAM_ERROR.getCode(),
                    "参数错误",
                    Map.of("password", "密码不能为空")
            );
        }
        if (!password.matches(PASSWORD_REGEX)) {
            throw new BusinessException(
                    ErrorCode.PARAM_ERROR.getCode(),
                    "参数错误",
                    Map.of("password", "密码仅支持大小写英文、数字和 _-@!#$%&*，长度为6-22位")
            );
        }
    }

    /**
     * 用户登录业务处理
     *
     * @param request 登录请求参数 (email, password)
     * @return LoginVO 包含 Token 和用户基本信息
     */
    @Transactional(rollbackFor = Exception.class)
    public LoginVO login(LoginDTO request) {
        // 0. 解密密码
        String realPassword = decryptPassword(request.getPassword());
        validateDecryptedPassword(realPassword);

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

    /**
     * 用户注册业务处理
     *
     * @param request 注册请求参数 (username, email, password)
     * @return RegisterVO 注册成功后的用户信息
     */
    @Transactional(rollbackFor = Exception.class)
    public RegisterVO register(RegisterDTO request) {
        log.info("开始处理用户注册请求: username={}, email={}", request.getUsername(), request.getEmail());

        // 1) 先校验邀请码是否可用（存在且未使用）。
        // 说明：这里是前置校验，后续仍会通过条件更新做并发安全校验。
        inviteCodeService.validateInviteCode(request.getInviteCode());

        // 2) 检查邮箱是否存在
        long emailCount = userService.count(new LambdaQueryWrapper<User>()
                .eq(User::getEmail, request.getEmail()));
        if (emailCount > 0) {
            log.warn("注册失败，邮箱已存在: {}", request.getEmail());
            throw new BusinessException(
                    ErrorCode.USER_EMAIL_ALREADY_EXISTS.getCode(),
                    ErrorCode.USER_EMAIL_ALREADY_EXISTS.getMessage(),
                    Map.of("email", "该邮箱已被注册")
            );
        }

        // 3) 解密并校验密码强度
        String realPassword = decryptPassword(request.getPassword());
        validateDecryptedPassword(realPassword);

        // 4) 预先生成可用 UID（避免邀请码消耗后再做复杂重试）
        Long uid = generateAvailableUid();

        // 5) 先将邀请码标记为已使用。
        // 关键点：register 方法本身有事务，若后续任一步失败（例如用户保存失败），
        // 本次邀请码更新会随事务一起回滚，保证“要么都成功，要么都失败”。
        inviteCodeService.consumeInviteCode(request.getInviteCode(), uid);

        // 6) 创建用户并落库
        User user = new User();
        user.setUid(uid);
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPassword(BCrypt.hashpw(realPassword));
        user.setStatus(1); // 1-正常

        try {
            userService.save(user);
        } catch (DuplicateKeyException e) {
            if (userService.count(new LambdaQueryWrapper<User>().eq(User::getEmail, request.getEmail())) > 0) {
                throw new BusinessException(
                        ErrorCode.USER_EMAIL_ALREADY_EXISTS.getCode(),
                        ErrorCode.USER_EMAIL_ALREADY_EXISTS.getMessage(),
                        Map.of("email", "该邮箱已被注册")
                );
            }
            log.error("用户注册失败: UID或唯一键冲突, uid={}, username={}", uid, request.getUsername(), e);
            throw new BusinessException(ErrorCode.SYSTEM_ERROR);
        }

        log.info("用户注册成功: uid={}, username={}", user.getUid(), user.getUsername());

        // 7) 返回VO
        return BeanUtil.copyProperties(user, RegisterVO.class);
    }

    /**
     * 生成一个当前可用的 9 位随机 UID。
     * 说明：
     * 1. 先做存在性检测，降低后续写库冲突概率；
     * 2. 最终唯一性仍由数据库主键约束兜底。
     */
    private Long generateAvailableUid() {
        int maxAttempts = 20;
        for (int i = 0; i < maxAttempts; i++) {
            long candidateUid = RandomUtil.randomLong(100000000, 999999999);
            boolean exists = userService.count(
                    new LambdaQueryWrapper<User>().eq(User::getUid, candidateUid)
            ) > 0;
            if (!exists) {
                return candidateUid;
            }
        }
        throw new BusinessException(ErrorCode.SYSTEM_ERROR.getCode(), "用户ID生成失败，请重试");
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
