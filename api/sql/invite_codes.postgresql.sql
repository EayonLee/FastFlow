/*
 * 表名: invite_codes
 * 作用: 存储邀请码
 * 适用数据库: PostgreSQL
 */

BEGIN;

DROP TABLE IF EXISTS invite_codes;

CREATE TABLE invite_codes (
    invite_code CHAR(6) PRIMARY KEY,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    used_by_uid BIGINT,
    used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE invite_codes IS '邀请码表';
COMMENT ON COLUMN invite_codes.invite_code IS '邀请码(6位字母数字)';
COMMENT ON COLUMN invite_codes.is_used IS '是否使用: false-未使用, true-已使用';
COMMENT ON COLUMN invite_codes.used_by_uid IS '使用人UID';
COMMENT ON COLUMN invite_codes.used_at IS '使用时间';
COMMENT ON COLUMN invite_codes.created_at IS '创建时间';

COMMIT;
