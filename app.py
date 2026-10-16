import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import pymysql

app = FastAPI()

def get_db():
    return pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="1234",
        database="government_ad_db",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

@app.get("/api/init-data")
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

            # 총 건수
            cur.execute("SELECT COUNT(*) AS cnt FROM ad_execution")
            total_count = cur.fetchone()['cnt']

        return {
            "success": True,
            "total_count": total_count,
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

@app.get("/api/summary")
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
            
            count_sql = "SELECT COUNT(*) AS cnt FROM ad_execution WHERE 1=1"
            count_params = []
            if year:
                count_sql += " AND 집행연도 = %s"
                count_params.append(year)
            cur.execute(count_sql, count_params)
            filtered_count = cur.fetchone()['cnt']
            
        return {"success": True, "summary": summary_rows, "filtered_count": filtered_count}
    except Exception as exc:
        print(f"❌ /api/summary 에러: {exc}")
        raise HTTPException(500, detail=str(exc))
    finally:
        conn.close()

@app.get("/api/search-ads")
def search_ads(
    keyword: str = "",
    org_type: str = "",
    media_type: str = "",
    year: str = "",
    month: str = "",
    sort_col: str = "",
    sort_dir: str = "ASC",
    limit: int = 2500,
    offset: int = 0
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

            # 필터링된 총 개수 및 총 집행금액 합계 계산
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
            total_sum = summary_res['total_sum'] or 0 if summary_res else 0

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

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>정부광고 집행내역 (22~26.09)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Malgun Gothic', sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #333; color: #fff; }
        .table { color: #e0e0e0; font-size: 13px; }
        .table-dark { background-color: #1a1a1a; }
        .form-control, .form-select { background-color: #2b2b2b; border-color: #444; color: #fff; }
        .form-control:focus, .form-select:focus { background-color: #333; color: #fff; border-color: #0d6efd; box-shadow: none; }
        .ai-banner { background: linear-gradient(135deg, #1f2937, #111827); border-left: 4px solid #3b82f6; }
        .search-summary-card { background: rgba(13, 110, 253, 0.1); border: 1px dashed #0d6efd; display: none; }
        th.sortable { cursor: pointer; user-select: none; transition: background-color 0.2s; }
        th.sortable:hover { background-color: #333 !important; color: #3b82f6; }
    </style>
</head>
<body class="p-4">
    <div class="container-fluid">
        <!-- 상단 헤더 -->
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>📊 정부광고 집행내역 (22~26.09)</h2>
            <div>
                <span class="badge bg-secondary p-2" id="dbTotalBadge">DB 전체 연동 건수: 로딩 중...</span>
                <span class="badge bg-primary p-2 ms-2" id="loadedCountBadge">현재 로드된 결과: 0건</span>
            </div>
        </div>

        <!-- AI 자동 분석 리포트 -->
        <div class="card ai-banner p-3 mb-4 shadow-sm">
            <h5 class="text-info fw-bold">🤖 자동 분석 리포트</h5>
            <p class="mb-0" id="aiReportText">데이터를 분석하고 있습니다...</p>
        </div>

        <!-- 중앙 시각화 및 요약 영역 -->
        <div class="row mb-4">
            <div class="col-lg-5 mb-3 mb-lg-0">
                <div class="card p-3 h-100">
                    <h5 class="card-title text-center mb-3">📈 매체구분별 총 집행 금액 비중</h5>
                    <div style="position: relative; height: 300px;">
                        <canvas id="mediaChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-lg-7">
                <div class="card p-3 h-100">
                    <h5 class="card-title mb-3">📌 매체구분별 광고 집행 요약표</h5>
                    <div class="table-responsive" style="max-height: 310px; overflow-y: auto;">
                        <table class="table table-sm table-dark table-hover align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>매체구분</th>
                                    <th>집행 건수</th>
                                    <th>총 집행 금액 (VAT 포함)</th>
                                </tr>
                            </thead>
                            <tbody id="summaryTableBody">
                                <tr><td colspan="3" class="text-center">로딩 중...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- 필터 및 검색 컨트롤 -->
        <div class="card p-3 mb-4">
            <div class="row g-2 align-items-center">
                <div class="col-md-2">
                    <select id="yearFilter" class="form-select form-select-sm" onchange="onYearFilterChange()">
                        <option value="">모든 연도</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select id="orgTypeFilter" class="form-select form-select-sm" onchange="fetchData(true)">
                        <option value="">모든 기관분류</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select id="mediaTypeFilter" class="form-select form-select-sm" onchange="fetchData(true)">
                        <option value="">모든 매체구분</option>
                    </select>
                </div>
                <div class="col-md-4">
                    <input type="text" id="keywordInput" class="form-control form-control-sm" placeholder="기관명, 매체명, 광고명 검색..." onkeyup="if(event.key==='Enter') fetchData(true)">
                </div>
                <div class="col-md-2 text-end">
                    <button class="btn btn-primary btn-sm w-100" onclick="fetchData(true)">검색</button>
                </div>
            </div>
        </div>

        <!-- 하단 상세 데이터 테이블 -->
        <div class="card p-3">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="mb-0">📋 상세 집행 내역</h5>
                <small class="text-muted">컬럼명을 클릭하면 정렬됩니다. 스크롤을 내리면 추가 데이터를 불러옵니다.</small>
            </div>

            <!-- 검색어/필터 맞춤형 요약 카드 배지 -->
            <div id="searchSummaryCard" class="card search-summary-card p-3 mb-3">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="badge bg-info text-dark me-2">🔍 맞춤 팩트체크 요약</span>
                        <span id="searchSummaryText">검색 결과가 없습니다.</span>
                    </div>
                    <div>
                        <strong class="text-warning" id="searchSummarySum">총 집행액: 0 원</strong>
                    </div>
                </div>
            </div>

            <div class="table-responsive" id="tableContainer" style="max-height: 500px; overflow-y: auto;">
                <table class="table table-sm table-dark table-hover align-middle">
                    <thead>
                        <tr>
                            <th class="sortable" onclick="sortTable('집행연도')">연도 <span id="sort_집행연도"></span></th>
                            <th class="sortable" onclick="sortTable('기관분류')">기관분류 <span id="sort_기관분류"></span></th>
                            <th class="sortable" onclick="sortTable('기관명')">기관명 <span id="sort_기관명"></span></th>
                            <th class="sortable" onclick="sortTable('매체구분')">매체구분 <span id="sort_매체구분"></span></th>
                            <th class="sortable" onclick="sortTable('매체명')">매체명 <span id="sort_매체명"></span></th>
                            <th class="sortable" onclick="sortTable('광고명')">광고명 <span id="sort_광고명"></span></th>
                            <th class="sortable" onclick="sortTable('광고시작일')">광고시작일 <span id="sort_광고시작일"></span></th>
                            <th class="sortable" onclick="sortTable('광고종료일')">광고종료일 <span id="sort_광고종료일"></span></th>
                            <th class="sortable text-end" onclick="sortTable('광고료')">광고료 <span id="sort_광고료"></span></th>
                            <th class="sortable text-end" onclick="sortTable('수수료')">수수료 <span id="sort_수수료"></span></th>
                            <th class="sortable text-end" onclick="sortTable('총계(VAT포함)')">총계(VAT포함) <span id="sort_총계(VAT포함)"></span></th>
                        </tr>
                    </thead>
                    <tbody id="dataTableBody">
                        <tr><td colspan="11" class="text-center">데이터를 불러오는 중입니다...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let myChart = null;
        let currentOffset = 0;
        const batchSize = 2500;
        let isLoading = false;
        let hasMore = true;

        let currentSortCol = '';
        let currentSortDir = 'ASC';

        function formatKoreanCurrency(amount) {
            if (!amount) return '0 원';
            const 조 = Math.floor(amount / 1000000000000);
            const 억 = Math.floor((amount % 1000000000000) / 100000000);
            const 만 = Math.floor((amount % 100000000) / 10000);
            
            let result = '';
            if (조 > 0) result += `${조.toLocaleString()}조 `;
            if (억 > 0) result += `${억.toLocaleString()}억 `;
            if (만 > 0) result += `${만.toLocaleString()}만 `;
            
            return result ? result + '원' : '0 원';
        }

        function formatDate(dateStr) {
            if (!dateStr) return '';
            let s = String(dateStr).trim();
            const reg = new RegExp('^\\\\d{6,8}$');
            if (/^\\d{6,8}$/.test(s) || reg.test(s)) {
                if (s.length === 8) {
                    return `${s.substring(2, 4)}.${s.substring(4, 6)}.${s.substring(6, 8)}`;
                } else if (s.length === 6) {
                    return `${s.substring(0, 2)}.${s.substring(2, 4)}.${s.substring(4, 6)}`;
                }
            }
            return s;
        }

        function sortTable(colName) {
            if (currentSortCol === colName) {
                currentSortDir = currentSortDir === 'ASC' ? 'DESC' : 'ASC';
            } else {
                currentSortCol = colName;
                currentSortDir = 'ASC';
            }

            const cols = ['집행연도', '기관분류', '기관명', '매체구분', '매체명', '광고명', '광고시작일', '광고종료일', '광고료', '수수료', '총계(VAT포함)'];
            cols.forEach(c => {
                const span = document.getElementById(`sort_${c}`);
                if (span) span.innerText = '';
            });

            const activeSpan = document.getElementById(`sort_${colName}`);
            if (activeSpan) {
                activeSpan.innerText = currentSortDir === 'ASC' ? ' ▲' : ' ▼';
            }

            fetchData(true);
        }

        async function initDashboard() {
            try {
                const res = await fetch('/api/init-data');
                const result = await res.json();
                if (result.success) {
                    document.getElementById('dbTotalBadge').innerText = `DB 전체 연동 건수: ${result.total_count.toLocaleString()}건`;
                    
                    const yearSelect = document.getElementById('yearFilter');
                    result.years.forEach(y => {
                        const opt = document.createElement('option');
                        opt.value = y;
                        opt.innerText = `${y}년도`;
                        yearSelect.appendChild(opt);
                    });

                    const orgSelect = document.getElementById('orgTypeFilter');
                    result.org_types.forEach(o => {
                        const opt = document.createElement('option');
                        opt.value = o;
                        opt.innerText = o;
                        orgSelect.appendChild(opt);
                    });

                    const mediaSelect = document.getElementById('mediaTypeFilter');
                    if (result.media_types) {
                        result.media_types.forEach(m => {
                            const opt = document.createElement('option');
                            opt.value = m;
                            opt.innerText = m;
                            mediaSelect.appendChild(opt);
                        });
                    }

                    updateTopVisuals(result.summary, result.total_count, '전체 기간(2022~2026.09.30)');
                }
            } catch (e) {
                console.error("초기화 실패:", e);
            }
            
            // 💡 초기화 완료 후 명확하게 상세 데이터 호출
            await fetchData(true);
        }

        async function onYearFilterChange() {
            const selectedYear = document.getElementById('yearFilter').value;
            const yearLabel = selectedYear ? `${selectedYear}년도` : '전체 기간(2022~2026.09.30)';
            
            try {
                const res = await fetch(`/api/summary?year=${selectedYear}`);
                const result = await res.json();
                if (result.success) {
                    updateTopVisuals(result.summary, result.filtered_count, yearLabel);
                }
            } catch (e) {
                console.error("요약 데이터 갱신 오류:", e);
            }

            fetchData(true);
        }

        function updateTopVisuals(summary, totalCount, periodLabel) {
            if (summary.length > 0) {
                const top = summary[0];
                const formattedSpend = formatKoreanCurrency(top.total_spend);
                document.getElementById('aiReportText').innerHTML = 
                    `현재 집계된 데이터에 따르면(집계기간: <strong>${periodLabel}</strong>), <strong>${top.매체구분}</strong> 부문이 총 <strong>${formattedSpend}</strong>으로 가장 높은 광고비 비중을 차지하고 있습니다.`;
            } else {
                document.getElementById('aiReportText').innerHTML = `선택하신 <strong>${periodLabel}</strong>에 해당하는 데이터가 없습니다.`;
            }

            const summaryBody = document.getElementById('summaryTableBody');
            summaryBody.innerHTML = '';
            if (summary.length === 0) {
                summaryBody.innerHTML = '<tr><td colspan="3" class="text-center">데이터가 없습니다.</td></tr>';
            } else {
                summary.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `<td><strong>${row.매체구분}</strong></td><td>${Number(row.ad_count).toLocaleString()} 건</td><td>${Number(row.total_spend).toLocaleString()} 원</td>`;
                    summaryBody.appendChild(tr);
                });
            }

            const labels = summary.map(i => i.매체구분);
            const dataVals = summary.map(i => i.total_spend);

            if (myChart) {
                myChart.data.labels = labels;
                myChart.data.datasets[0].data = dataVals;
                myChart.update();
            } else {
                const ctx = document.getElementById('mediaChart').getContext('2d');
                myChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: dataVals,
                            backgroundColor: ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { 
                            legend: { 
                                position: 'bottom', 
                                labels: { color: '#e0e0e0' } 
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.raw || 0;
                                        const formatted = formatKoreanCurrency(value);
                                        return ` ${label}: ${formatted}`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }

        async function fetchData(isReset = false) {
            if (isLoading) return;
            isLoading = true;

            const tbody = document.getElementById('dataTableBody');
            if (isReset) {
                currentOffset = 0;
                hasMore = true;
                tbody.innerHTML = '<tr><td colspan="11" class="text-center text-info">데이터를 불러오는 중입니다...</td></tr>';
            }

            const year = document.getElementById('yearFilter').value;
            const orgType = document.getElementById('orgTypeFilter').value;
            const mediaType = document.getElementById('mediaTypeFilter').value;
            const keyword = document.getElementById('keywordInput').value;

            const url = `/api/search-ads?year=${encodeURIComponent(year)}&org_type=${encodeURIComponent(orgType)}&media_type=${encodeURIComponent(mediaType)}&keyword=${encodeURIComponent(keyword)}&sort_col=${encodeURIComponent(currentSortCol)}&sort_dir=${encodeURIComponent(currentSortDir)}&limit=${batchSize}&offset=${currentOffset}`;

            try {
                const res = await fetch(url);
                const result = await res.json();

                if (result.success) {
                    const summaryCard = document.getElementById('searchSummaryCard');
                    if (keyword || year || orgType || mediaType) {
                        summaryCard.style.display = 'block';
                        let condText = [];
                        if (keyword) condText.push(`키워드: "${keyword}"`);
                        if (year) condText.push(`연도: ${year}년`);
                        if (orgType) condText.push(`기관분류: ${orgType}`);
                        if (mediaType) condText.push(`매체구분: ${mediaType}`);
                        
                        document.getElementById('searchSummaryText').innerText = `${condText.join(' | ')} 조건 일치`;
                        document.getElementById('searchSummarySum').innerText = `총 집행액: ${Number(result.total_sum).toLocaleString()} 원 (${formatKoreanCurrency(result.total_sum)})`;
                    } else {
                        summaryCard.style.display = 'none';
                    }

                    if (isReset) tbody.innerHTML = '';

                    const rows = result.data;
                    document.getElementById('loadedCountBadge').innerText = `현재 로드된 결과: ${currentOffset + rows.length}건 (총 필터: ${result.total_filtered.toLocaleString()}건)`;

                    if (rows.length === 0 && isReset) {
                        tbody.innerHTML = '<tr><td colspan="11" class="text-center text-warning">검색 결과가 없습니다.</td></tr>';
                        hasMore = false;
                        isLoading = false;
                        return;
                    }

                    rows.forEach(r => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${r.집행연도 || ''}</td>
                            <td>${r.기관분류 || ''}</td>
                            <td>${r.기관명 || ''}</td>
                            <td>${r.매체구분 || ''}</td>
                            <td>${r.매체명 || ''}</td>
                            <td>${r.광고명 || ''}</td>
                            <td>${formatDate(r.광고시작일)}</td>
                            <td>${formatDate(r.광고종료일)}</td>
                            <td class="text-end">${Number(r.광고료 || 0).toLocaleString()}</td>
                            <td class="text-end">${Number(r.수수료 || 0).toLocaleString()}</td>
                            <td class="text-end">${Number(r.총계 || r['총계(VAT포함)'] || 0).toLocaleString()}</td>
                        `;
                        tbody.appendChild(tr);
                    });

                    currentOffset += rows.length;
                    if (currentOffset >= result.total_filtered) {
                        hasMore = false;
                    }
                }
            } catch (e) {
                console.error("데이터 로드 오류:", e);
                tbody.innerHTML = `<tr><td colspan="11" class="text-center text-danger">데이터 로드 중 에러 발생: ${e.message}</td></tr>`;
            } finally {
                isLoading = false;
            }
        }

        document.getElementById('tableContainer').addEventListener('scroll', function() {
            const el = this;
            if (el.scrollHeight - el.scrollTop <= el.clientHeight + 50) {
                if (hasMore && !isLoading) {
                    fetchData(false);
                }
            }
        });

        window.onload = initDashboard;
    </script>
</body>
</html>
    """