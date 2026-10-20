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

-- 기사 작성·검수 저장용 표. 기존 광고 표와 분리한다.

CREATE TABLE IF NOT EXISTS news_articles (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    base_year SMALLINT NOT NULL,
    current_year SMALLINT NOT NULL,
    title VARCHAR(300) NOT NULL DEFAULT '',
    body MEDIUMTEXT NOT NULL,
    fact_sheet LONGTEXT NOT NULL,
    settings_json TEXT NOT NULL,
    generation_record LONGTEXT NULL,
    generation_status VARCHAR(10) NOT NULL DEFAULT '대기',
    generation_token VARCHAR(36) NULL,
    generation_error VARCHAR(300) NULL,
    status VARCHAR(10) NOT NULL DEFAULT '검토대기',
    revision INT NOT NULL DEFAULT 1,
    review_revision INT NULL,
    review_checks TEXT NULL,
    reviewer VARCHAR(80) NULL,
    reviewed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CHECK (base_year BETWEEN 2022 AND 2026 AND current_year BETWEEN 2022 AND 2026 AND base_year <> current_year),
    CHECK (status IN ('검토대기', '보류', '승인')),
    CHECK (generation_status IN ('대기', '생성중', '완료', '실패')),
    INDEX idx_news_status (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS news_reviews (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    article_id BIGINT UNSIGNED NOT NULL,
    article_revision INT NOT NULL,
    reviewer VARCHAR(80) NOT NULL,
    checks_json TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    action VARCHAR(10) NOT NULL,
    comment TEXT NOT NULL,
    reviewed_at DATETIME(6) NOT NULL,
    CONSTRAINT fk_news_review_article FOREIGN KEY (article_id) REFERENCES news_articles(id),
    CHECK (action IN ('검수', '승인', '보류')),
    INDEX idx_news_review_article (article_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
