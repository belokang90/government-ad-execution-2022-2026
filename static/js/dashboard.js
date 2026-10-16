// 정부광고 대시보드: 검색·정렬·차트·추가 로딩
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
