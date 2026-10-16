// Node 기본 테스트만 사용한다. DB·네트워크·추가 패키지는 필요 없다.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/js/dashboard.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
const row = name => ({집행연도: '2025', 기관명: name, 광고료: 110, '총계(VAT포함)': 121});
const overview = (count = 3000) => ({
    success: true, total_count: count, total_sum: 363000,
    summary: [{매체구분: '인터넷', ad_count: count, total_spend: 363000}],
    years: ['2025'], org_types: ['지자체'], media_types: ['인터넷'],
});

function harness() {
    const elements = new Map();
    class Element {
        constructor() { this.value = ''; this.innerHTML = ''; this.innerText = ''; this.style = {}; this.handlers = {}; this.children = []; }
        appendChild(node) { this.children.push(node); this.innerHTML += node.innerHTML || ''; }
        insertAdjacentHTML(position, html) { this.innerHTML += html; }
        addEventListener(name, handler) { this.handlers[name] = handler; }
        getContext() { return {}; }
    }
    const get = id => {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
    };
    const requests = [];
    const errors = [];
    const context = vm.createContext({
        document: {getElementById: get, createElement: () => new Element()},
        console: {error: (...args) => errors.push(args)},
        URLSearchParams, AbortController,
        fetch: (url, options = {}) => new Promise(resolve => {
            requests.push({url: new URL(url, 'http://localhost'), options,
                resolve: (body, ok = true) => resolve({ok, status: ok ? 200 : 500, json: async () => body})});
        }),
    });
    const boot = vm.runInContext(source, context);
    return {get, requests, errors, context, boot,
        run: code => vm.runInContext(code, context)};
}

async function finishBoot(h, count = 3000) {
    h.requests[0].resolve(overview(count));
    h.requests[1].resolve(overview(count));
    h.requests[2].resolve({success: true, data: [row('최초기관')], total_filtered: null, total_sum: null});
    await h.boot;
}

test('첫 상세 행은 느린 초기 집계·차트 다운로드를 기다리지 않는다', async () => {
    const h = harness();
    assert.deepEqual(h.requests.map(r => r.url.pathname), ['/api/init-data', '/api/filter-options', '/api/search-ads']);
    assert.equal(h.requests[2].url.searchParams.get('include_totals'), 'false');
    assert.equal(h.requests[2].url.searchParams.get('limit'), '2500');
    h.requests[2].resolve({success: true, data: [row('먼저 표시할 기관')], total_filtered: null, total_sum: null});
    await flush();
    assert.match(h.get('dataTableBody').innerHTML, /먼저 표시할 기관/);
    assert.match(h.get('loadedCountBadge').innerText, /집계 중/);
    h.requests[0].resolve(overview());
    await h.boot;
    assert.match(h.get('loadedCountBadge').innerText, /총 필터: 3,000건/);
    assert.equal(h.errors.length, 0);
    // 늦게 내려받은 차트도 마지막으로 받은 집계를 표시해야 한다.
    h.context.Chart = class {
        constructor(ctx, options) { this.data = options.data; }
        update() {}
    };
    h.get('chartLibrary').handlers.load();
    assert.equal(h.run('myChart.data.labels[0]'), '인터넷');
});

test('추가 페이지는 합계를 재요청하지 않고 2,500건 다음부터 이어 붙인다', async () => {
    const h = harness();
    h.requests[0].resolve(overview());
    h.requests[2].resolve({success: true, data: Array.from({length: 2500}, (_, i) => row(`기관${i}`))});
    await h.boot;
    const next = h.run('fetchData(false)');
    assert.equal(h.requests[3].url.searchParams.get('include_totals'), 'false');
    assert.equal(h.requests[3].url.searchParams.get('offset'), '2500');
    h.requests[3].resolve({success: true, data: Array.from({length: 500}, () => row('추가기관'))});
    await next;
    assert.equal(h.run('currentOffset'), 3000);
    assert.equal(h.run('hasMore'), false);
    assert.match(h.get('loadedCountBadge').innerText, /3000건 \(총 필터: 3,000건\)/);
});

test('명시적으로 다시 검색하면 합계를 새로 요청한다', async () => {
    const h = harness();
    await finishBoot(h);
    h.get('keywordInput').value = '새 검색';
    const done = h.run('fetchData(true)');
    assert.equal(h.requests[3].url.searchParams.get('keyword'), '새 검색');
    assert.equal(h.requests[3].url.searchParams.get('include_totals'), 'true');
    h.requests[3].resolve({success: true, data: [row('새기관')], total_filtered: 1, total_sum: 121});
    await done;
    assert.match(h.get('searchSummaryText').innerText, /새 검색/);
    assert.match(h.get('searchSummarySum').innerText, /121 원/);
    assert.equal(h.run('hasMore'), false);
});

test('빠르게 필터를 바꿔도 느린 이전 응답이 새 결과를 덮지 않는다', async () => {
    const h = harness();
    await finishBoot(h);
    h.get('keywordInput').value = '이전';
    const older = h.run('fetchData(true)');
    h.get('keywordInput').value = '최신';
    const newer = h.run('fetchData(true)');
    assert.equal(h.requests[3].options.signal.aborted, true);
    h.requests[4].resolve({success: true, data: [row('최신기관')], total_filtered: 1, total_sum: 121});
    await newer;
    h.requests[3].resolve({success: true, data: [row('이전기관')], total_filtered: 2, total_sum: 242});
    await older;
    assert.match(h.get('dataTableBody').innerHTML, /최신기관/);
    assert.doesNotMatch(h.get('dataTableBody').innerHTML, /이전기관/);
    assert.match(h.get('searchSummaryText').innerText, /최신/);
});

test('초기 집계 실패 시 행을 먼저 보존하고 합계를 별도로 복구한다', async () => {
    const h = harness();
    h.requests[0].resolve({success: false});
    h.requests[2].resolve({success: true, data: [row('복구기관')]});
    await flush();
    assert.match(h.get('dataTableBody').innerHTML, /복구기관/);
    assert.equal(h.requests[3].url.searchParams.get('limit'), '0');
    assert.equal(h.requests[3].url.searchParams.get('include_totals'), 'true');
    h.requests[3].resolve({success: true, data: [], total_filtered: 1, total_sum: 121});
    await h.boot;
    assert.match(h.get('loadedCountBadge').innerText, /총 필터: 1건/);
    assert.match(h.get('dataTableBody').innerHTML, /복구기관/);
});

test('연도 변경 시 상세 검색과 상단 요약을 동시에 요청한다', async () => {
    const h = harness();
    await finishBoot(h);
    h.get('yearFilter').value = '2025';
    const done = h.run('onYearFilterChange()');
    assert.deepEqual(h.requests.slice(3).map(r => r.url.pathname), ['/api/search-ads', '/api/summary']);
    h.requests[3].resolve({success: true, data: [row('연도기관')], total_filtered: 1, total_sum: 121});
    await flush();
    assert.match(h.get('dataTableBody').innerHTML, /연도기관/);
    h.requests[4].resolve({success: true, summary: overview().summary, filtered_count: 1});
    await done;
    assert.match(h.get('aiReportText').innerHTML, /2025년도/);
});


test('상단 요약은 선택 목록 조회가 끝나기 전에 표시된다', async () => {
    const h = harness();
    assert.equal(h.requests[0].url.searchParams.get('include_filters'), 'false');
    h.requests[0].resolve({...overview(), years: [], org_types: [], media_types: []});
    h.requests[2].resolve({success: true, data: [row('요약 우선 시험')]});
    await h.boot;
    assert.match(h.get('aiReportText').innerHTML, /인터넷/);
    assert.match(h.get('dbTotalBadge').innerText, /3,000건/);
    assert.equal(h.get('yearFilter').children.length, 0);
    h.requests[1].resolve(overview());
    await flush();
    assert.equal(h.get('yearFilter').children[0].value, '2025');
    assert.equal(h.get('orgTypeFilter').children[0].value, '지자체');
    assert.equal(h.get('mediaTypeFilter').children[0].value, '인터넷');
    assert.equal(h.errors.length, 0);
});

test('선택 목록에 오류가 생겨도 요약과 상세 데이터 표시를 막지 않는다', async () => {
    const h = harness();
    h.requests[1].resolve({}, false);
    h.requests[0].resolve({...overview(), years: [], org_types: [], media_types: []});
    h.requests[2].resolve({success: true, data: [row('목록 오류 시험')]});
    await h.boot;
    assert.match(h.get('aiReportText').innerHTML, /인터넷/);
    assert.match(h.get('dataTableBody').innerHTML, /목록 오류 시험/);
    assert.match(h.get('loadedCountBadge').innerText, /총 필터: 3,000건/);
    assert.equal(h.errors.length, 1);
});
