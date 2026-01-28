/*
 Navicat Premium Data Transfer

 Source Server Type    : MySQL
 Source Server Version : 80000
 Source Schema         : fastflow

 Target Server Type    : MySQL
 Target Server Version : 80000
 File Encoding         : 65001

 Date: 22/01/2026 15:30:00
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for workflows
-- ----------------------------
DROP TABLE IF EXISTS `workflows`;
CREATE TABLE `workflows` (
  `id` varchar(24) COLLATE utf8mb4_general_ci NOT NULL COMMENT '工作流ID',
  `name` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '工作流名称',
  `description` varchar(500) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '工作流描述',
  `creator` bigint NOT NULL COMMENT '创建者UID',
  `config` longtext COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '工作流配置JSON',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`id`),
  KEY `idx_creator` (`creator`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='工作流表';

SET FOREIGN_KEY_CHECKS = 1;
