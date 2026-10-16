# app.py를 항목별로 나눈 구조

## 무엇이 달라졌나

원래 `app.py`에는 DB 접속 정보, SQL, API, HTML, CSS, JavaScript가 들어 있었습니다. 같은 기능을 역할별 파일로 옮겼습니다. 실행 명령은 계속 `uvicorn app:app --reload`입니다.

| 기존 내용 | 옮긴 위치 | 역할 |
|---|---|---|
| `app = FastAPI()` | `app.py` | 웹 앱 생성 |
| MySQL 호스트·계정·비밀번호 | `.env` → `config.py` | PC마다 다른 접속 정보 관리 |
| `get_db()` | `database.py` | 실제 DB 연결 열기 |
| `init_data()` | `routers/ads.py` | 최초 화면에 필요한 전체 요약·선택 목록 |
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
| `initDashboard()` | 최초 요약·필터 목록을 읽은 뒤 상세 검색 |
| `onYearFilterChange()` | 연도 변경 시 상단 요약과 상세 목록 갱신 |
| `updateTopVisuals()` | 자동 요약 문장·집계표·차트 갱신 |
| `fetchData()` | 검색 API를 호출하고 결과 행·총액 표시 |
| `scroll` 이벤트 | 표 아래에 가까워지면 다음 묶음 요청 |
| `window.onload` | 페이지가 열리면 초기화 시작 |

## 어디를 수정하면 되나

- **검색창을 추가:** HTML에 입력창 → JavaScript에서 입력값 읽기 → API 매개변수와 SQL 조건 추가
- **색상·폰트 변경:** CSS
- **조회·합계 기준 변경:** `routers/ads.py`의 SQL
- **DB 비밀번호 변경:** `.env`
- **기사 초안 기능 추가:** 별도 API와 생성 서비스 추가. [구현 안내](article-draft-plan.md) 참고

## 이번 분리의 범위

기존 조회 API의 주소·검색 조건·응답 구조와 화면의 동작 코드를 유지했습니다. DB 접속 정보는 소스에 적는 방식에서 `.env`를 읽는 방식으로 바꾸고, CSV 적재 스크립트도 같은 설정을 읽도록 연결했습니다. CSV 적재에 필요한 pandas를 패키지 목록에 추가했습니다.

필터를 빠르게 연속 변경할 때 진행 중인 검색 때문에 새 요청이 무시될 수 있는 기존 동작, 월 값이 `01`로 채워지는 적재 방식, 중복 적재 방지 기능은 이번 구조 분리에서 고치지 않았습니다. 기사 기능을 실제로 붙이기 전에는 이 동작과 데이터 품질을 별도로 점검해야 합니다.
