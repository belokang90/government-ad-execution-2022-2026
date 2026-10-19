# app.py를 항목별로 나눈 구조

## 무엇이 달라졌나

원래 `app.py`에는 DB 접속 정보, SQL, API, HTML, CSS, JavaScript가 들어 있었습니다. 같은 기능을 역할별 파일로 옮겼습니다. 실행 명령은 계속 `uvicorn app:app --reload`입니다.

| 기존 내용 | 옮긴 위치 | 역할 |
|---|---|---|
| `app = FastAPI()` | `app.py` | 웹 앱 생성 |
| MySQL 호스트·계정·비밀번호 | `.env` → `config.py` | PC마다 다른 접속 정보 관리 |
| `get_db()` | `database.py` | 실제 DB 연결 열기 |
| `init_data()`, `filter_options()` | `routers/ads.py` | 전체 요약과 선택 목록을 각각 조회 |
| `get_summary()` | `routers/ads.py` | 선택한 연도의 매체별 건수·금액 |
| `search_ads()` | `routers/ads.py` | 검색 조건·정렬·일부 행 조회·전체 조건 합계 |
| `home()`의 HTML | `templates/index.html` | 화면 구조 |
| `<style>` 내용 | `static/css/dashboard.css` | 색상·배치·표 스타일 |
| `<script>` 내용 | `static/js/dashboard.js` | 화면에서 실행되는 기능 |

`templates`는 화면 파일을 모은 폴더 이름입니다. 현재는 템플릿 엔진 없이 `FileResponse`로 HTML 파일을 보냅니다. HTML이 CSS와 JavaScript 파일을 각각 요청하고, JavaScript가 API를 호출합니다.

## JavaScript 안의 항목

| 코드 이름 | 쉬운 뜻 |
|---|---|
| `myChart` | 현재 그래프 보관 |
| `currentOffset`, `batchSize`, `hasMore` | 어디까지 읽었는지, 한 번에 몇 건 읽는지, 더 읽을 자료가 있는지 |
| `currentSortCol`, `currentSortDir` | 현재 정렬 항목과 오름·내림차순 |
| `formatKoreanCurrency()` | 큰 금액을 조·억·만 단위로 표현 |
| `formatDate()` | 날짜 표시 방식 변경 |
| `sortTable()` | 정렬 방향·표시 변경 후 다시 검색 |
| `initDashboard()`, `loadInitialData()`, `loadFilterOptions()` | 요약·필터·상세 요청을 병렬로 시작하고 상세 행부터 표시 |
| `onYearFilterChange()` | 연도 변경 시 상단 요약과 상세 목록 갱신 |
| `updateTopVisuals()` | 자동 요약 문장·집계표·차트 갱신 |
| `fetchData()` | 검색 API를 호출하고 결과 행·총액 표시 |
| `scroll` 이벤트 | 표 아래에 가까워지면 다음 묶음 요청 |
| 파일 끝의 `initDashboard()` 호출 | HTML 요소가 준비되면 초기화 시작, 외부 차트 라이브러리는 비동기로 로드 |

## 어디를 수정하면 되나

- **검색창을 추가:** HTML에 입력창 → JavaScript에서 입력값 읽기 → API 매개변수와 SQL 조건 추가
- **색상·폰트 변경:** CSS
- **조회·합계 기준 변경:** `routers/ads.py`의 SQL
- **DB 비밀번호 변경:** `.env`
- **기사 초안 기능 추가:** 별도 API와 생성 서비스 추가. [구현 안내](article-draft-plan.md) 참고

## 이번 분리의 범위

기존 조회 API의 주소·검색 조건과 기본 응답을 유지하면서 서버·화면·설정을 나눴습니다. DB 접속 정보는 `.env`에서 읽고, CSV 적재 스크립트도 같은 설정을 사용합니다. CSV 적재용 pandas와 MySQL 인증용 PyMySQL 추가 의존성은 `requirements.txt`로 설치합니다.

이후 로딩 개선으로 상세 목록·상단 요약·필터를 병렬로 읽고, 중복 전체 집계를 줄였습니다. 새 검색 시 이전 요청을 취소하며 오래된 응답을 적용하지 않습니다. `include_totals`·`include_filters`는 기존 API 기본값을 유지하는 추가 옵션이고, 선택 목록 전용 API도 추가했습니다. 서버 터미널에는 DB 연결·집계·API 처리 시간이 기록됩니다.

새 설치용 `schema.sql`은 요약 집계용 `idx_ad_summary_cover` 인덱스를 포함합니다. 이미 사용 중인 DB는 [설치 안내의 기존 DB 절차](../INSTALL.md#11-기존-pc에서-수정본만-업데이트)에 따라 별도로 확인합니다. 앱 실행 시 DB 구조를 자동으로 변경하지 않습니다.

월 값이 `01`로 채워지는 기존 적재 방식과 CSV 재실행 시 중복될 수 있는 동작은 유지합니다. 기사 기능을 실제로 붙이기 전에 집계 근거와 데이터 품질을 점검해야 합니다.
