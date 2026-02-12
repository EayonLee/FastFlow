/*
 * 文件名: model_configs.sql
 * 作用: 定义模型配置表的数据库结构
 * 实现功能: 创建 model_configs 表，用于存储大模型的连接配置信息，包括 API Key、Base URL 等。
 * 注意事项:
 *   1. id 为自增主键。
 *   2. mode_name 具有唯一性约束，不可重复。
 *   3. 包含了创建时间和更新时间的自动维护字段。
 */

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for model_configs
-- ----------------------------
DROP TABLE IF EXISTS `model_configs`;
CREATE TABLE `model_configs` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `model_name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '模型名称',
  `model_id` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '模型ID',
  `api_key` varchar(255) COLLATE utf8mb4_general_ci NOT NULL COMMENT 'API 密钥',
  `api_base` varchar(255) COLLATE utf8mb4_general_ci NOT NULL COMMENT 'API 地址',
  `api_mode` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT 'API 模式（如：openai、claude、google_gemini）',
  `user_group_id` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '所属用户组ID',
  `sort_order` int NOT NULL DEFAULT 1 COMMENT '排序值（越小越靠前）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_model_name` (`model_name`)
) ENGINE=InnoDB AUTO_INCREMENT=10000 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='模型配置表';

SET FOREIGN_KEY_CHECKS = 1;
