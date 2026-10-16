-- 새 학습 환경용 예시. 기존 표의 구조나 데이터를 변경하지 않는다.
-- 이 파일 자체는 CSV를 적재하지 않는다.
CREATE DATABASE IF NOT EXISTS government_ad_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE government_ad_db;

CREATE TABLE IF NOT EXISTS ad_execution (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    기관분류 TEXT,
    기관명 TEXT,
    매체구분 TEXT,
    매체명 TEXT,
    광고명 TEXT,
    광고시작일 VARCHAR(64),
    광고종료일 VARCHAR(64),
    광고료 DECIMAL(20, 2) NOT NULL DEFAULT 0,
    수수료 DECIMAL(20, 2) NOT NULL DEFAULT 0,
    `총계(VAT포함)` DECIMAL(20, 2) NOT NULL DEFAULT 0,
    집행년월 VARCHAR(7),
    집행연도 VARCHAR(4),
    INDEX idx_ad_year (집행연도)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
