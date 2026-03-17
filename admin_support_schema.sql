ALTER TABLE `agent_users`
  ADD COLUMN IF NOT EXISTS `role` VARCHAR(20) NOT NULL DEFAULT 'user',
  ADD COLUMN IF NOT EXISTS `is_admin` TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS `is_active` TINYINT(1) NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS `agent_support_requests` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `page_name` VARCHAR(50) NOT NULL,
  `issue` VARCHAR(255) NOT NULL,
  `expected_outcome` VARCHAR(255) NOT NULL,
  `note` TEXT DEFAULT NULL,
  `status` ENUM('open','in_progress','resolved','closed') NOT NULL DEFAULT 'open',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_support_user_status` (`user_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

UPDATE `agent_users`
SET `role` = 'admin',
    `is_admin` = 1,
    `is_active` = 1
WHERE `email` = 'pranjalsingh20032007@gmail.com';
