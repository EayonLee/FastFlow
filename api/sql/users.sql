/*
 Navicat Premium Data Transfer

 Source Server Type    : MySQL
 Source Server Version : 80000
 Source Schema         : fastflow

 Target Server Type    : MySQL
 Target Server Version : 80000
 File Encoding         : 65001

 Date: 21/01/2026 15:30:00
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `uid` bigint NOT NULL COMMENT 'UID (9位随机数字)',
  `username` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '用户名称 (唯一)',
  `email` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '用户邮箱',
  `password` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '加密密码',
  `status` tinyint NOT NULL DEFAULT '1' COMMENT '账号状态：1-正常, 2-封禁, 3-注销',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`uid`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户表';

SET FOREIGN_KEY_CHECKS = 1;
