-- 처음 설치할 때 사용하는 DB·표 생성 파일.
-- 기존 DB·표가 있으면 그대로 둔다. 자료 적재는 별도 단계에서 한 번만 한다.
-- 이 파일만 새 SQL 탭으로 열어서 실행한다.
CREATE DATABASE IF NOT EXISTS government_ad_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE government_ad_db;

CREATE TABLE IF NOT EXISTS ad_execution (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    기관분류 TEXT,
    기관명 TEXT,
    매체구분 VARCHAR(50),
    매체명 TEXT,
    광고명 TEXT,
    광고시작일 VARCHAR(64),
    광고종료일 VARCHAR(64),
    광고료 DECIMAL(20, 2) NOT NULL DEFAULT 0,
    수수료 DECIMAL(20, 2) NOT NULL DEFAULT 0,
    `총계(VAT포함)` DECIMAL(20, 2) NOT NULL DEFAULT 0,
    집행년월 VARCHAR(7),
    집행연도 VARCHAR(4),
    INDEX idx_ad_year (집행연도),
    INDEX idx_ad_summary_cover (매체구분, `총계(VAT포함)`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
