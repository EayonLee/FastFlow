/*
 * 表名: model_configs
 * 作用: 存储 LiteLLM 模型接入配置（模型标识、provider、网关地址、透传参数、启用开关）
 * 适用数据库: PostgreSQL
 */

BEGIN;

DROP TABLE IF EXISTS model_configs;

CREATE TABLE model_configs (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_id VARCHAR(150) NOT NULL,
    provider VARCHAR(50),
    api_key VARCHAR(255) NOT NULL,
    base_url VARCHAR(255),
    model_params_json TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 1,
    user_group_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_model_name UNIQUE (model_name)
);

COMMENT ON TABLE model_configs IS '模型配置表';
COMMENT ON COLUMN model_configs.id IS '主键ID';
COMMENT ON COLUMN model_configs.model_name IS '模型展示名称';
COMMENT ON COLUMN model_configs.model_id IS '模型标识（示例：moonshot/kimi-k2.5）';
COMMENT ON COLUMN model_configs.provider IS 'LiteLLM provider（可选，示例：openai/dashscope/moonshot）';
COMMENT ON COLUMN model_configs.api_key IS 'API 密钥';
COMMENT ON COLUMN model_configs.base_url IS '模型网关地址（可选）';
COMMENT ON COLUMN model_configs.model_params_json IS 'LiteLLM 透传参数（JSON 字符串）';
COMMENT ON COLUMN model_configs.enabled IS '是否启用：true启用 false禁用';
COMMENT ON COLUMN model_configs.sort_order IS '排序值（越小越靠前）';
COMMENT ON COLUMN model_configs.user_group_id IS '所属用户组ID';
COMMENT ON COLUMN model_configs.created_at IS '创建时间';
COMMENT ON COLUMN model_configs.updated_at IS '修改时间';

CREATE OR REPLACE FUNCTION set_model_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_model_configs_updated_at
BEFORE UPDATE ON model_configs
FOR EACH ROW
EXECUTE FUNCTION set_model_configs_updated_at();

INSERT INTO model_configs (
    id,
    model_name,
    model_id,
    provider,
    api_key,
    base_url,
    model_params_json,
    enabled,
    sort_order,
    user_group_id,
    created_at,
    updated_at
) VALUES
    (
        10000,
        'Kimi-K2',
        'moonshot/kimi-k2-turbo-preview',
        'moonshot',
        'xxx',
        'https://api.moonshot.cn/v1',
        NULL,
        TRUE,
        1,
        '0',
        '2026-01-23 17:44:18',
        '2026-02-12 11:18:11'
    ),
    (
        10001,
        'Qwen3.5-Plus（推荐）',
        'dashscope/qwen3.5-plus',
        'dashscope',
        'xxx',
        'https://dashscope.aliyuncs.com/compatible-mode/v1',
        '{"enable_thinking": true}',
        TRUE,
        2,
        '0',
        '2026-02-16 22:11:47',
        '2026-02-16 22:13:56'
    );

SELECT setval('model_configs_id_seq', COALESCE((SELECT MAX(id) FROM model_configs), 1), TRUE);

COMMIT;
