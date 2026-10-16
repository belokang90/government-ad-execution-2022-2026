# 정부광고 집행내역 대시보드

2022~2026년 정부광고 CSV를 MySQL에 저장하고, 웹 화면에서 검색·집계하는 학습용 프로젝트입니다. 파일명에 표시된 자료 기준일은 **2026년 9월 30일**입니다. 2026년 자료를 연간 확정 실적으로 해석하면 안 됩니다.

코딩을 처음 접하는 사람도 수정할 위치를 찾을 수 있도록, 서버·DB 연결·화면·디자인·화면 동작을 파일별로 나누었습니다.

## 1. 현재 가능한 기능

- 기관명·매체명·광고명 통합 검색
- 연도·기관분류·매체구분 필터
- 연도별 매체구분 집계표와 도넛 차트
- 검색 조건에 맞는 전체 건수와 총 집행액 표시
- 상세 표의 열 제목을 클릭한 정렬
- 2,500건씩 불러오는 스크롤 추가 로딩
- 광고시작일·종료일 및 광고료·수수료·VAT 포함 총계 표시

상단의 **‘자동 분석 리포트’는 집계 결과를 정해진 문장에 넣는 기능**입니다. 현재 OpenAI API를 호출하거나 기사 초안을 생성하지 않습니다. 기사 초안 기능을 붙이는 방법은 [OpenAI 기사 초안 구현 안내](docs/article-draft-plan.md)에 정리했습니다.

상단 차트·요약표는 **연도 필터**를 따릅니다. 기관분류·매체구분·검색어는 **상세 목록과 검색 요약 금액**에 적용됩니다. 두 영역의 집계 범위를 구분해서 읽어야 합니다.

## 2. 파일별 역할

| 파일 | 쉬운 설명 | 수정하는 경우 |
|---|---|---|
| `app.py` | 앱 시작점. 화면·API·정적 파일을 연결 | 새 기능 연결 |
| `config.py` | `.env`에서 DB 설정과 프로젝트 경로 읽기 | 설정 방식 변경 |
| `database.py` | MySQL 연결 함수 | DB 연결 방식 변경 |
| `routers/ads.py` | 초기 목록·연도 요약·광고 검색 API와 SQL | 검색 조건·집계 변경 |
| `templates/index.html` | 제목·버튼·검색창·표 등 화면 구조 | 화면 항목 추가 |
| `static/css/dashboard.css` | 색상·크기·배치 | 디자인 변경 |
| `static/js/dashboard.js` | 검색 요청·정렬·차트·스크롤 로딩 | 버튼 동작 변경 |
| `data/*.csv` | 연도별 원자료 | 자료 대조 |
| `data/load_all_years.py` | CSV를 MySQL에 추가 적재 | 데이터 적재 |
| `schema.sql` | 새 학습용 DB·표를 만드는 예시 | 처음 설치 |
| `.env.example` | DB 설정 양식 | `.env`로 복사해서 사용 |
| `requirements.txt` | 필요한 파이썬 패키지 목록 | 설치·환경 준비 |
| `docs/code-guide.md` | 기존 `app.py` 내용별 해설 | 코드 구조 학습 |
| `docs/article-draft-plan.md` | OpenAI 기사 초안 기능 설계·코드 예시 | 다음 기능 개발 |

기존 `public/index.html`, `README copy.md`, `migration_constraints.sql`에는 **날씨·기사 CRUD 실습** 내용이 들어 있습니다. 현재 정부광고 앱은 이 파일들을 사용하지 않습니다. 정부광고 설치 시 날씨용 SQL을 실행하지 마세요.

## 3. 준비할 것

- Python 3.10 이상
- 실행 중인 MySQL 서버와 접속 계정
- PowerShell 또는 VS Code 터미널

FastAPI는 요청을 받는 서버 도구, PyMySQL은 파이썬과 MySQL을 연결하는 도구, pandas는 CSV 표를 읽는 도구입니다. 화면에는 Bootstrap과 Chart.js를 사용하며, 외부 CDN 접속이 필요합니다.

## 4. 설치·실행 — Windows PowerShell

저장소를 받은 뒤 **`app.py`가 있는 폴더**에서 실행합니다.

```powershell
git clone https://github.com/belokang90/government_ad_app.git
cd government_ad_app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`를 열어 본인 PC의 MySQL 정보를 입력합니다.

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=본인의_MySQL_비밀번호
DB_NAME=government_ad_db
```

`.env`는 비밀번호를 담으므로 GitHub에 올리지 않습니다. 기존 `.gitignore`에서 제외하고 있습니다. 서버와 CSV 적재 스크립트 모두 같은 `.env`를 읽습니다.

### 처음 DB를 만드는 경우

MySQL Workbench에서 `schema.sql`을 열어 실행합니다. 이 파일은 **새 환경을 위한 표 구조 예시**이며, 이미 존재하는 표의 구조를 수정하거나 데이터를 삭제하지 않습니다. 기존 DB가 있다면 먼저 아래 항목을 확인합니다.

```sql
USE government_ad_db;
SHOW COLUMNS FROM ad_execution;
SELECT COUNT(*) AS 전체건수 FROM ad_execution;
SELECT 집행연도, COUNT(*) AS 건수,
       SUM(`총계(VAT포함)`) AS 총액
FROM ad_execution
GROUP BY 집행연도;
```

### CSV를 처음 넣는 경우

```powershell
.\.venv\Scripts\python.exe data/load_all_years.py
```

**이 스크립트는 추가 적재 방식입니다.** 이미 넣은 자료를 다시 실행하면 중복될 수 있습니다. 중복 확인·백업 없이 다시 실행하지 마세요. 10,000건 단위로 커밋하므로 도중 실패해도 앞서 저장한 자료는 남을 수 있습니다.

현재 적재 코드는 `집행년월`을 실제 광고 날짜에서 계산하지 않고 **해당 연도의 `01`로 채웁니다.** 따라서 월별 집계의 근거로 쓰면 안 됩니다. `집행연도`는 파일별 연도에서 채웁니다.

### 웹 서버 실행

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

- 대시보드: <http://127.0.0.1:8000>
- API 확인 화면: <http://127.0.0.1:8000/docs>

웹 서버를 실행하는 명령에는 OpenAI API 키가 필요하지 않습니다.

## 5. API 목록

| 방식 | 주소 | 역할 |
|---|---|---|
| GET | `/` | 대시보드 화면 |
| GET | `/api/init-data` | 전체 건수·매체 요약·필터 선택 목록 |
| GET | `/api/summary?year=2025` | 해당 연도 매체 요약·건수 |
| GET | `/api/search-ads` | 조건 검색·정렬·페이지 조회·전체 조건 합계 |

검색 API의 조건은 `keyword`, `org_type`, `media_type`, `year`, `month`, `sort_col`, `sort_dir`, `limit`, `offset`입니다. `month`는 기존 API에만 있고 화면 선택란은 없습니다. 앞서 설명한 적재 방식 때문에 현재 월 조건을 실제 월별 실적으로 사용하면 안 됩니다.

`limit`·`offset`은 화면에 가져올 행의 범위입니다. 응답의 `total_filtered`·`total_sum`은 그 페이지뿐 아니라 **동일 검색 조건에 맞는 전체 행**을 집계합니다. SQL 값은 매개변수로 전달하고, 정렬 열은 허용 목록에서 선택합니다.

## 6. 데이터를 기사에 쓸 때 확인할 점

- 파일명의 기간과 실제 자료 수록 범위가 일치하는지 원자료에서 확인
- `총계(VAT포함)`과 `광고료`·`수수료`의 정의·단위 확인
- CSV 건수·금액과 DB 집계 대조 및 중복 적재 확인
- 2026년 일부 기간과 다른 연도 전체를 그대로 비교하지 않기
- 상단 요약과 상세 검색의 집계 범위 구분
- 화면의 억·만 단위 요약은 만 원 미만 금액을 생략하므로, 기사에는 정확한 원 단위 합계 대조

CSV만으로 자료 제공기관·광고 집행 사유·적정성·특혜 여부는 확인할 수 없습니다. 해당 내용은 출처 문서와 추가 취재가 필요합니다. 원자료 제공기관의 링크와 이용 조건은 저장소에 확인 자료가 없어 확정해 적지 않았습니다.

## 7. 동작 검증

DB 없이 화면 경로와 API 연결을 확인하는 테스트입니다. 실제 MySQL 및 원자료 일치 검증을 대신하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 8. 다음 기능: 기사 초안

검색 조건을 서버에 보내고, 서버가 DB 전체 검색 결과의 건수·금액·기간을 계산한 뒤 OpenAI Responses API로 전달하는 방식입니다. AI에는 계산된 사실을 문장으로 작성하게 하고, 화면에는 초안과 집계 근거를 함께 보여줍니다.

[구현 순서·코드 예시·오류 처리·검수 기준 보기](docs/article-draft-plan.md)
