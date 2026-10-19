-- 기존 DB에 요약 집계용 인덱스만 추가한다. 기존 자료·열·인덱스를 삭제하지 않는다.
-- Workbench에서 이 파일 자체를 새 탭으로 열어 전체 실행한다.
-- 같은 이름의 인덱스가 이미 있으면 추가 작업을 생략한다.
-- 전제: 매체구분은 VARCHAR(50), 총계(VAT포함)는 DECIMAL인 기존 운영 DB.
-- README의 자료형 확인 절차를 먼저 따른다. TEXT 열을 임의로 변경하지 않는다.

SET @summary_index_exists = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = 'government_ad_db'
      AND table_name = 'ad_execution'
      AND index_name = 'idx_ad_summary_cover'
);

SET @summary_index_sql = IF(
    @summary_index_exists > 0,
    'SELECT ''idx_ad_summary_cover 인덱스가 이미 있어 추가를 생략했습니다.'' AS result',
    'CREATE INDEX idx_ad_summary_cover ON government_ad_db.ad_execution (`매체구분`, `총계(VAT포함)`)'
);

PREPARE summary_index_statement FROM @summary_index_sql;
EXECUTE summary_index_statement;
DEALLOCATE PREPARE summary_index_statement;
