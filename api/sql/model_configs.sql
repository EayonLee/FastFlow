/*
 * 表名: model_configs
 * 作用: 存储 LiteLLM 模型接入配置（模型标识、provider、网关地址、透传参数、启用开关）
 */

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for model_configs
-- ----------------------------
DROP TABLE IF EXISTS `model_configs`;
CREATE TABLE `model_configs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `model_name` varchar(100) NOT NULL COMMENT '模型展示名称',
  `litellm_model` varchar(150) NOT NULL COMMENT 'LiteLLM 模型标识（示例：moonshot/kimi-k2.5）',
  `provider` varchar(50) DEFAULT NULL COMMENT 'LiteLLM provider（可选，示例：openai/dashscope/moonshot）',
  `api_key` varchar(255) NOT NULL COMMENT 'API 密钥',
  `base_url` varchar(255) DEFAULT NULL COMMENT '模型网关地址（可选）',
  `model_params_json` text COMMENT 'LiteLLM 透传参数（JSON 字符串）',
  `enabled` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用：1启用 0禁用',
  `sort_order` int(11) NOT NULL DEFAULT '1' COMMENT '排序值（越小越靠前）',
  `user_group_id` varchar(50) NOT NULL COMMENT '所属用户组ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_name` (`model_name`)
) ENGINE=InnoDB AUTO_INCREMENT=10002 DEFAULT CHARSET=utf8mb4 COMMENT='模型配置表';

-- ----------------------------
-- Records of model_configs
-- ----------------------------
BEGIN;
INSERT INTO `model_configs` (`id`, `model_name`, `litellm_model`, `provider`, `api_key`, `base_url`, `model_params_json`, `enabled`, `sort_order`, `user_group_id`, `created_at`, `updated_at`) VALUES (10000, 'Kimi-K2', 'moonshot/kimi-k2-turbo-preview', 'moonshot', 'xxx', 'https://api.moonshot.cn/v1', NULL, 1, 1, '0', '2026-01-23 17:44:18', '2026-02-12 11:18:11');
INSERT INTO `model_configs` (`id`, `model_name`, `litellm_model`, `provider`, `api_key`, `base_url`, `model_params_json`, `enabled`, `sort_order`, `user_group_id`, `created_at`, `updated_at`) VALUES (10001, 'Qwen3.5-Plus（推荐）', 'dashscope/qwen3.5-plus', 'dashscope', 'xxx', 'https://dashscope.aliyuncs.com/compatible-mode/v1', NULL, 1, 2, '0', '2026-02-16 22:11:47', '2026-02-16 22:13:56');
COMMIT;

SET FOREIGN_KEY_CHECKS = 1;
