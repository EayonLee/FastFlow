/*
 * 表名: users
 * 作用: 存储系统用户账号信息
 * 适用数据库: PostgreSQL
 */

BEGIN;

DROP TABLE IF EXISTS users;

CREATE TABLE users (
    uid BIGINT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    password VARCHAR(100) NOT NULL,
    status SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_email UNIQUE (email),
    CONSTRAINT chk_users_status CHECK (status IN (1, 2, 3))
);

COMMENT ON TABLE users IS '用户表';
COMMENT ON COLUMN users.uid IS 'UID (9位随机数字)';
COMMENT ON COLUMN users.username IS '用户名称';
COMMENT ON COLUMN users.email IS '用户邮箱';
COMMENT ON COLUMN users.password IS '加密密码';
COMMENT ON COLUMN users.status IS '账号状态：1-正常, 2-封禁, 3-注销';
COMMENT ON COLUMN users.created_at IS '创建时间';
COMMENT ON COLUMN users.updated_at IS '修改时间';

CREATE OR REPLACE FUNCTION set_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_users_updated_at();

INSERT INTO users (
    uid,
    username,
    email,
    password,
    status,
    created_at,
    updated_at
) VALUES (
    254908813,
    'Eayon',
    'lizhengtai@360.cn',
    '$2a$10$U.1KPKeDUjA4y5K3.DZAZuQrlpCICDnNnR.3BKvq/XxTAGLg5ckDS',
    1,
    '2026-01-21 19:19:00',
    '2026-01-21 19:19:00'
);

COMMIT;
