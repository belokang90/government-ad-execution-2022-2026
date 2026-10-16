"""정부광고 초기 정보·연도별 요약·조건 검색 API."""

from fastapi import APIRouter, HTTPException

from database import get_db

router = APIRouter(prefix="/api", tags=["정부광고"])

@router.get("/init-data")
def init_data():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # 전체 요약 정보
            cur.execute("""
                SELECT
                    매체구분,
                    COUNT(*) AS ad_count,
                    SUM(`총계(VAT포함)`) AS total_spend
                FROM ad_execution
                GROUP BY 매체구분
                ORDER BY total_spend DESC
            """)
            summary_rows = cur.fetchall()

            # 기관분류 목록
            cur.execute("SELECT DISTINCT 기관분류 FROM ad_execution WHERE 기관분류 IS NOT NULL AND 기관분류 != '' ORDER BY 기관분류")
            org_types = [row['기관분류'] for row in cur.fetchall()]

            # 매체구분 목록
            cur.execute("SELECT DISTINCT 매체구분 FROM ad_execution WHERE 매체구분 IS NOT NULL AND 매체구분 != '' ORDER BY 매체구분")
            media_types = [row['매체구분'] for row in cur.fetchall()]

            # 연도 목록
            cur.execute("SELECT DISTINCT 집행연도 AS yr FROM ad_execution WHERE 집행연도 IS NOT NULL AND 집행연도 != '' ORDER BY yr DESC")
            years = [row['yr'] for row in cur.fetchall()]

            # 같은 전체 자료를 다시 COUNT/SUM하지 않고 매체별 집계에서 합산한다.
            total_count = sum(row['ad_count'] for row in summary_rows)
            total_sum = sum(row['total_spend'] or 0 for row in summary_rows)

        return {
            "success": True,
            "total_count": total_count,
            "total_sum": total_sum,
            "summary": summary_rows,
            "org_types": org_types,
            "media_types": media_types,
            "years": years
        }
    except Exception as exc:
        print(f"❌ /api/init-data 에러: {exc}")
        raise HTTPException(500, detail=str(exc))
    finally:
        conn.close()

@router.get("/summary")
def get_summary(year: str = ""):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT
                    매체구분,
                    COUNT(*) AS ad_count,
                    SUM(`총계(VAT포함)`) AS total_spend
                FROM ad_execution
                WHERE 1=1
            """
            params = []
            if year:
                sql += " AND 집행연도 = %s"
                params.append(year)

            sql += " GROUP BY 매체구분 ORDER BY total_spend DESC"
            cur.execute(sql, params)
            summary_rows = cur.fetchall()

            # GROUP BY의 COUNT 합계는 동일 조건의 전체 건수와 같다.
            filtered_count = sum(row['ad_count'] for row in summary_rows)

        return {"success": True, "summary": summary_rows, "filtered_count": filtered_count}
    except Exception as exc:
        print(f"❌ /api/summary 에러: {exc}")
        raise HTTPException(500, detail=str(exc))
    finally:
        conn.close()

@router.get("/search-ads")
def search_ads(
    keyword: str = "",
    org_type: str = "",
    media_type: str = "",
    year: str = "",
    month: str = "",
    sort_col: str = "",
    sort_dir: str = "ASC",
    limit: int = 2500,
    offset: int = 0,
    include_totals: bool = True
):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            where_clauses = ["1=1"]
            params = []

            if keyword:
                where_clauses.append("(기관명 LIKE %s OR 매체명 LIKE %s OR 광고명 LIKE %s)")
                kw = f"%{keyword}%"
                params.extend([kw, kw, kw])

            if org_type:
                where_clauses.append("기관분류 = %s")
                params.append(org_type)

            if media_type:
                where_clauses.append("매체구분 = %s")
                params.append(media_type)

            if year:
                where_clauses.append("집행연도 = %s")
                params.append(year)

            if month:
                where_clauses.append("집행년월 LIKE %s")
                params.append(f"%{month}")

            where_str = " AND ".join(where_clauses)

            # 데이터 조회
            sql = f"SELECT * FROM ad_execution WHERE {where_str}"

            allowed_sort_cols = {
                '집행연도': '집행연도',
                '기관분류': '기관분류',
                '기관명': '기관명',
                '매체구분': '매체구분',
                '매체명': '매체명',
                '광고명': '광고명',
                '광고시작일': '광고시작일',
                '광고종료일': '광고종료일',
                '광고료': '광고료',
                '수수료': '수수료',
                '총계(VAT포함)': '`총계(VAT포함)`'
            }

            if sort_col in allowed_sort_cols:
                direction = "DESC" if sort_dir.upper() == "DESC" else "ASC"
                sql += f" ORDER BY {allowed_sort_cols[sort_col]} {direction}"

            sql += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(sql, params)
            rows = cur.fetchall()

            # 최초 검색만 전체 합계를 구한다. 추가 페이지는 화면의 동일 검색 집계를 재사용한다.
            # 기본값은 True이므로 기존 API 사용자는 같은 응답을 받는다.
            total_filtered = None
            total_sum = None
            if include_totals:
                count_sql = f"""
                    SELECT
                        COUNT(*) AS cnt,
                        SUM(`총계(VAT포함)`) AS total_sum
                    FROM ad_execution
                    WHERE {where_str}
                """
                cur.execute(count_sql, params[:-2])
                summary_res = cur.fetchone()
                total_filtered = summary_res['cnt'] if summary_res else 0
                total_sum = (summary_res['total_sum'] or 0) if summary_res else 0

        return {
            "success": True,
            "data": rows,
            "total_filtered": total_filtered,
            "total_sum": total_sum
        }
    except Exception as exc:
        print(f"❌ /api/search-ads 에러: {exc}")
        raise HTTPException(500, detail=str(exc))
    finally:
        conn.close()
