-- 기존 정부광고 자료를 유지하고 기사·검수 표 두 개만 추가한다.
-- .env의 DB_NAME이 다르면 아래 government_ad_db를 그 이름으로 바꾼다.
USE government_ad_db;

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
