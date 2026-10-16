// 정부광고 대시보드: 검색·정렬·차트·추가 로딩
let myChart = null;
let currentOffset = 0;
const batchSize = 2500;
let isLoading = false;
let hasMore = true;
let activeRequestId = 0;
let activeController = null;
let currentTotals = null;
let pendingChartSummary = null;

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
    const reg = new RegExp('^\\d{6,8}$');
    if (/^\d{6,8}$/.test(s) || reg.test(s)) {
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

async function loadFilterOptions() {
    try {
        const res = await fetch('/api/filter-options');
        if (!res.ok) throw new Error(`선택 목록 요청 실패 (${res.status})`);
        const result = await res.json();
        if (result.success) {
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

        }
    } catch (e) {
        console.error("선택 목록 로드 실패:", e);
    }
}

async function loadInitialData() {
    try {
        const summaryRequest = fetch('/api/init-data?include_filters=false');
        // 선택 목록은 병렬로 채우되 상단 요약의 표시를 막지 않는다.
        loadFilterOptions();
        const res = await summaryRequest;
        if (!res.ok) throw new Error(`초기 요약 요청 실패 (${res.status})`);
        const result = await res.json();
        if (result.success) {
            document.getElementById('dbTotalBadge').innerText = `DB 전체 연동 건수: ${result.total_count.toLocaleString()}건`;

            if (!document.getElementById('yearFilter').value) {
                updateTopVisuals(result.summary, result.total_count, '전체 기간(2022~2026.09.30)');
            }
            return {total_filtered: result.total_count, total_sum: result.total_sum};
        }
    } catch (e) {
        console.error("초기화 실패:", e);
    }

    return null;
}


async function initDashboard() {
    // 요약, 선택 목록, 첫 상세 페이지를 각각 요청한다.
    // 상세 행은 요약을 기다리지 않고 표시하고, 총액·건수만 같은 초기 집계에서 받는다.
    const totalsPromise = loadInitialData();
    await fetchData(true, totalsPromise);
}

async function onYearFilterChange() {
    const selectedYear = document.getElementById('yearFilter').value;
    const yearLabel = selectedYear ? `${selectedYear}년도` : '전체 기간(2022~2026.09.30)';
    const detailRequest = fetchData(true);
    try {
        const res = await fetch(`/api/summary?year=${encodeURIComponent(selectedYear)}`);
        const result = await res.json();
        if (result.success && document.getElementById('yearFilter').value === selectedYear) {
            updateTopVisuals(result.summary, result.filtered_count, yearLabel);
        }
    } catch (e) {
        console.error("요약 데이터 갱신 오류:", e);
    }
    await detailRequest;
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

    drawChart(summary);
}

function drawChart(summary) {
    pendingChartSummary = summary;
    // 외부 차트 파일이 늦어도 검색·표 표시를 막지 않는다.
    if (typeof Chart === 'undefined') return;

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

async function fetchData(isReset = false, bootstrapTotalsPromise = null) {
    if (isLoading && !isReset) return;
    if (isReset && activeController) activeController.abort();
    const requestId = ++activeRequestId;
    const controller = new AbortController();
    activeController = controller;
    isLoading = true;

    const tbody = document.getElementById('dataTableBody');
    if (isReset) {
        currentOffset = 0;
        currentTotals = null;
        hasMore = true;
        tbody.innerHTML = '<tr><td colspan="11" class="text-center text-info">데이터를 불러오는 중입니다...</td></tr>';
    }

    const year = document.getElementById('yearFilter').value;
    const orgType = document.getElementById('orgTypeFilter').value;
    const mediaType = document.getElementById('mediaTypeFilter').value;
    const keyword = document.getElementById('keywordInput').value;
    // 최초 전체 조회만 초기 집계를 공유한다. 필터 검색은 매번 새로 집계한다.
    const initialTotals = !year && !orgType && !mediaType && !keyword
        ? bootstrapTotalsPromise : null;
    const includeTotals = !initialTotals && (isReset || !currentTotals);
    const params = new URLSearchParams({
        year, org_type: orgType, media_type: mediaType, keyword,
        sort_col: currentSortCol, sort_dir: currentSortDir,
        limit: String(batchSize), offset: String(currentOffset),
        include_totals: String(includeTotals),
    });

    try {
        const res = await fetch(`/api/search-ads?${params}`, {signal: controller.signal});
        if (!res.ok) throw new Error(`조회 요청 실패 (${res.status})`);
        const result = await res.json();
        if (requestId !== activeRequestId || !result.success) return;

        if (isReset) tbody.innerHTML = '';
        const rows = result.data;
        if (rows.length === 0 && isReset) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center text-warning">검색 결과가 없습니다.</td></tr>';
            hasMore = false;
        } else {
            // 같은 2,500개 행을 한 번에 파싱·삽입해 반복 DOM 변경을 줄인다.
            tbody.insertAdjacentHTML('beforeend', rows.map(r => `
                <tr>
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
                </tr>
            `).join(''));
        }
        currentOffset += rows.length;
        document.getElementById('loadedCountBadge').innerText =
            `현재 로드된 결과: ${currentOffset}건 (전체 건수 집계 중...)`;

        if (includeTotals) {
            currentTotals = result;
        } else if (initialTotals) {
            let totals = await initialTotals;
            if (requestId !== activeRequestId) return;
            if (!totals) {
                // 초기 정보 요청 실패 시 기존 검색 API에서 합계만 다시 받는다.
                const totalsParams = new URLSearchParams(params);
                totalsParams.set('include_totals', 'true');
                totalsParams.set('limit', '0');
                totalsParams.set('offset', '0');
                const totalsResponse = await fetch(`/api/search-ads?${totalsParams}`, {signal: controller.signal});
                if (!totalsResponse.ok) throw new Error('전체 건수 집계에 실패했습니다.');
                totals = await totalsResponse.json();
                if (!totals.success) throw new Error('전체 건수 집계에 실패했습니다.');
            }
            if (requestId !== activeRequestId) return;
            currentTotals = totals;
        }

        if (currentTotals) {
            const summaryCard = document.getElementById('searchSummaryCard');
            if (keyword || year || orgType || mediaType) {
                summaryCard.style.display = 'block';
                const condText = [];
                if (keyword) condText.push(`키워드: "${keyword}"`);
                if (year) condText.push(`연도: ${year}년`);
                if (orgType) condText.push(`기관분류: ${orgType}`);
                if (mediaType) condText.push(`매체구분: ${mediaType}`);
                document.getElementById('searchSummaryText').innerText = `${condText.join(' | ')} 조건 일치`;
                document.getElementById('searchSummarySum').innerText = `총 집행액: ${Number(currentTotals.total_sum).toLocaleString()} 원 (${formatKoreanCurrency(currentTotals.total_sum)})`;
            } else {
                summaryCard.style.display = 'none';
            }
            document.getElementById('loadedCountBadge').innerText = `현재 로드된 결과: ${currentOffset}건 (총 필터: ${currentTotals.total_filtered.toLocaleString()}건)`;
            hasMore = currentOffset < currentTotals.total_filtered;
        }
    } catch (e) {
        if (e.name === 'AbortError' || requestId !== activeRequestId) return;
        console.error("데이터 로드 오류:", e);
        tbody.innerHTML = `<tr><td colspan="11" class="text-center text-danger">데이터 로드 중 에러 발생: ${e.message}</td></tr>`;
    } finally {
        if (requestId === activeRequestId) isLoading = false;
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

document.getElementById('chartLibrary').addEventListener('load', () => {
    if (pendingChartSummary !== null) drawChart(pendingChartSummary);
});

// 스크립트는 body 끝에 있으므로 이미지·차트 파일의 load 이벤트를 기다릴 필요가 없다.
initDashboard();
