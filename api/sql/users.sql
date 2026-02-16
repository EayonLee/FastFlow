/*
 Navicat Premium Dump SQL

 Source Server         : 11.121.246.88
 Source Server Type    : MySQL
 Source Server Version : 50744 (5.7.44)
 Source Host           : 11.121.246.88:3306
 Source Schema         : fastflow

 Target Server Type    : MySQL
 Target Server Version : 50744 (5.7.44)
 File Encoding         : 65001

 Date: 17/02/2026 00:23:53
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `uid` bigint(20) NOT NULL COMMENT 'UID (9位随机数字)',
  `username` varchar(50) NOT NULL COMMENT '用户名称 (唯一)',
  `email` varchar(100) DEFAULT NULL COMMENT '用户邮箱',
  `password` varchar(100) NOT NULL COMMENT '加密密码',
  `status` tinyint(4) NOT NULL DEFAULT '1' COMMENT '账号状态：1-正常, 2-封禁, 3-注销',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '修改时间',
  PRIMARY KEY (`uid`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ----------------------------
-- Records of users
-- ----------------------------
BEGIN;
INSERT INTO `users` (`uid`, `username`, `email`, `password`, `status`, `created_at`, `updated_at`) VALUES (254908813, 'Eayon', 'lizhengtai@360.cn', '$2a$10$U.1KPKeDUjA4y5K3.DZAZuQrlpCICDnNnR.3BKvq/XxTAGLg5ckDS', 1, '2026-01-21 19:19:00', '2026-01-21 19:19:00');
COMMIT;

SET FOREIGN_KEY_CHECKS = 1;
