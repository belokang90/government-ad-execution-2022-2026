# 설치·실행 안내 — Windows

프로젝트 소개와 기능 설명은 [README](README.md)에 있습니다.

이 문서는 **Windows 10·11, 일반적인 64비트 PC, Python과 DB를 같은 PC에서 실행하는 경우**를 기준으로 작성했습니다. 처음 설치하는 사람은 1번부터 순서대로 따라 하세요. 별도의 유료 API 키는 필요하지 않습니다.

> **이미 데이터가 정상적으로 뜨는 PC라면:** [11. 기존 PC에서 수정본만 업데이트](#11-기존-pc에서-수정본만-업데이트)로 가세요. DB 생성과 CSV 적재를 처음부터 다시 하지 않습니다.
>
> **SQL 실행 위치:** SQL은 MySQL Workbench에서 실행합니다. `powershell` 명령은 VS Code의 PowerShell 터미널에서 실행합니다. 두 입력창을 구분하세요.

## 목차

1. [필요한 프로그램과 설치 순서](#1-필요한-프로그램과-설치-순서)
2. [Python 설치](#2-python-설치)
3. [MySQL Server·Workbench 설치와 접속](#3-mysql-serverworkbench-설치와-접속)
4. [프로젝트 다운로드와 VS Code 열기](#4-프로젝트-다운로드와-vs-code-열기)
5. [가상환경 만들기와 패키지 설치](#5-가상환경-만들기와-패키지-설치)
6. [DB 접속 정보 설정](#6-db-접속-정보-설정)
7. [처음 설치할 때 DB·표 생성](#7-처음-설치할-때-db표-생성)
8. [CSV를 DB에 한 번만 적재](#8-csv를-db에-한-번만-적재)
9. [웹 서버 실행과 접속](#9-웹-서버-실행과-접속)
10. [다음 날 다시 실행·종료](#10-다음-날-다시-실행종료)
11. [기존 PC에서 수정본만 업데이트](#11-기존-pc에서-수정본만-업데이트)
12. [다른 PC로 옮기기·DB 백업](#12-다른-pc로-옮기기db-백업)
13. [오류가 나거나 자료가 안 보일 때](#13-오류가-나거나-자료가-안-보일-때)
14. [공식 설치 문서](#14-공식-설치-문서)

## 1. 필요한 프로그램과 설치 순서

| 준비물 | 하는 일 | 이 안내에서의 선택 |
|---|---|---|
| Python | 파이썬으로 작성된 웹 앱 실행 | **3.13 계열 64비트**로 안내 |
| MySQL Server | 광고 데이터를 실제로 저장하고 조회·집계 | **Community 8.0 계열**로 안내 |
| MySQL Workbench | SQL 실행·DB 확인·백업을 화면으로 작업 | Server와 함께 설치 |
| VS Code | 프로젝트 폴더·설정 파일·터미널 열기 | 설치 권장 |
| 웹브라우저 | 완성된 대시보드 보기 | Chrome·Edge 등 |

VS Code와 Workbench는 편집·관리 도구입니다. 앱 실행 자체에는 Python과 MySQL Server가 필요합니다. 아래에서는 초보자가 화면을 보고 작업할 수 있도록 두 관리 도구도 사용합니다.

**GitHub 파일을 받는 것만으로 MySQL에 자료가 들어가지는 않습니다.** 코드 다운로드 → 패키지 설치 → DB 설정 → CSV 적재 → 앱 실행 순서로 준비해야 합니다. ZIP 다운로드 방식은 Git 설치가 필요하지 않습니다. Node.js와 OpenAI 패키지도 현재 앱 실행에는 필요하지 않습니다.

## 2. Python 설치

1. [Python 공식 Windows 다운로드](https://www.python.org/downloads/windows/)를 엽니다.
2. **Python 3.13 계열**에서 일반 설치 파일인 **Windows installer (64-bit)**를 받습니다. 아래 가상환경 생성 명령도 3.13을 지정합니다.
3. 설치 파일을 실행하고 첫 화면에서 **Add python.exe to PATH** 또는 **Add Python to PATH** 항목을 체크합니다. 터미널에서 Python을 찾을 수 있게 하는 설정입니다.
4. 기본 설치를 진행합니다. pip와 Python 실행 도구도 기본 설치에 포함됩니다.
5. 설치가 끝나면 열려 있던 VS Code·터미널을 닫았다가 다시 엽니다.
6. Windows 시작 메뉴에서 **PowerShell**을 찾아 열고 다음 명령을 입력합니다.

```powershell
py -3.13 --version
```

`Python 3.13.x`와 같은 버전이 나오면 준비됐습니다. `x` 자리는 설치한 세부 버전마다 다릅니다. `py`를 찾을 수 없다는 오류가 나오면 [13번](#13-오류가-나거나-자료가-안-보일-때)을 확인하세요.

이미 3.12 또는 3.13으로 이 앱을 정상 실행 중이라면 재설치할 필요는 없습니다. 새로 설치하는 사람은 위 안내의 3.13 계열을 사용하면 뒤 명령을 그대로 따라 할 수 있습니다.

## 3. MySQL Server·Workbench 설치와 접속

### 3-1. 설치 파일 받기

1. [MySQL 공식 Installer 다운로드](https://dev.mysql.com/downloads/installer/)를 엽니다. 이 안내는 Server와 Workbench를 함께 선택할 수 있는 **8.0 계열 Installer**를 사용합니다.
2. 인터넷이 연결된 PC에서는 이름에 `web-community`가 들어간 설치 파일을 사용할 수 있습니다. 파일 크기가 더 큰 `community` 설치 파일도 사용할 수 있습니다.
3. 다운로드 과정에서 가입·로그인 화면이 나오면 계정 생성 없이 다운로드하는 링크를 선택할 수 있습니다.
4. 설치 프로그램을 실행합니다. 설치 유형에서 **Custom**을 선택하고, 설치할 제품으로 **MySQL Server 8.0의 64비트 버전과 MySQL Workbench 8.0**을 추가합니다.
5. 필요한 구성요소 설치가 표시되면 안내에 따라 설치한 뒤 다음으로 진행합니다. Server까지 설치돼야 합니다. Workbench만 설치하면 DB 서버가 생기지 않습니다.

설치 파일 설명에 32비트라고 적혀 있어도 Installer 자체의 표시일 수 있습니다. 실제 제품을 선택할 때 Server의 64비트 버전을 확인하세요.

### 3-2. 서버 설정

| 설정 내용 | 새 PC에서 사용할 값 |
|---|---|
| 사용 환경 | 개발용 PC에 해당하는 기본 선택 |
| 접속 방식·포트 | TCP/IP, `3306` |
| 관리자 계정 | `root` |
| 관리자 비밀번호 | **본인이 정한 비밀번호를 따로 기록** |
| 인증 방식 | 설치 프로그램의 권장 기본값 |
| Windows 서비스 | 서비스로 등록하고 Windows 시작 시 실행 |

다음 단계로 진행해 설정을 적용하고 서버를 시작합니다. 이미 다른 MySQL이 설치되어 있거나 포트 충돌이 보이면 기존 DB를 지우거나 재설정하지 말고, 현재 서버의 접속 정보를 먼저 확인하세요.

### 3-3. Workbench로 접속 확인

1. MySQL Workbench를 엽니다.
2. 첫 화면에 방금 만든 로컬 접속 항목이 있으면 엽니다. 없으면 접속 목록 옆의 **＋**로 새 접속을 만듭니다.
3. 접속 이름은 알아보기 쉽게 정하고, 호스트는 `127.0.0.1`, 포트는 `3306`, 사용자 이름은 `root`로 입력합니다.
4. 접속 테스트 버튼을 누르고 방금 정한 비밀번호를 입력합니다.
5. 연결에 성공하면 해당 접속을 열어 둡니다.

이때 사용한 **호스트·포트·사용자·비밀번호**를 6번에서 앱에도 입력합니다.

## 4. 프로젝트 다운로드와 VS Code 열기

### 4-1. Git 없이 ZIP으로 받기

1. [이 저장소](https://github.com/belokang90/government_ad_app)를 엽니다.
2. 왼쪽 위 브랜치 선택이 **`main`**인지 확인합니다.
3. 초록색 코드 버튼을 눌러 **Download ZIP**을 선택합니다.
4. 받은 ZIP을 우클릭해 **모두 압축 풀기**로 원하는 작업 폴더에 풉니다. ZIP 안에서 직접 실행하지 않습니다.
5. 압축을 푼 뒤 `app.py`, `requirements.txt`, `schema.sql`, `data`가 함께 있는 폴더를 찾습니다. 기본 이름은 `government_ad_app-main`일 수 있습니다.

### 4-2. VS Code에서 폴더 열기

1. [VS Code 공식 다운로드](https://code.visualstudio.com/download)에서 Windows용 설치 파일을 받아 설치합니다.
2. VS Code에서 **파일 → 폴더 열기**를 선택합니다.
3. 위에서 찾은 **`app.py`가 있는 폴더**를 엽니다. 그 바깥 폴더를 잘못 고르면 뒤의 명령이 파일을 찾지 못합니다.
4. 상단 **터미널 → 새 터미널**을 선택합니다.
5. 터미널 종류를 **PowerShell**로 선택합니다. 아래 설치 명령은 PowerShell 기준입니다.
6. 다음 명령으로 현재 폴더를 확인합니다.

```powershell
Get-ChildItem app.py, requirements.txt, schema.sql
```

파일 3개가 모두 나오면 맞는 폴더입니다. 명령을 실행할 때는 코드 블록 안의 내용만 복사하고 Enter를 누릅니다. 각 명령이 끝나서 입력할 수 있는 줄이 다시 나타난 다음, 다음 명령을 실행하세요.

Git을 이미 사용하는 사람은 ZIP 대신 다음 명령으로 받을 수 있습니다. 그다음 만들어진 폴더를 VS Code로 열면 됩니다.

```powershell
git clone --branch main https://github.com/belokang90/government_ad_app.git
cd government_ad_app
```

## 5. 가상환경 만들기와 패키지 설치

**가상환경**은 이 프로젝트에서 쓸 Python과 패키지를 따로 모아두는 폴더입니다. 여기서는 폴더 이름을 `.venv`로 만듭니다.

이 절의 명령은 **VS Code의 PowerShell 터미널**, `app.py`가 있는 폴더에서 실행합니다.

### 5-1. 가상환경 생성 — 처음 한 번

```powershell
py -3.13 -m venv .venv
```

완료되면 왼쪽 파일 목록에 `.venv` 폴더가 생깁니다. 아무 메시지 없이 입력 줄로 돌아와도 정상입니다. 이미 이 PC에서 정상 사용 중인 `.venv`가 있다면 다시 만들지 않습니다.

이후에는 `.venv` 안의 Python을 경로로 직접 실행합니다. **가상환경 활성화 명령이나 PowerShell 실행 정책 변경은 필요하지 않습니다.**

### 5-2. 패키지 설치 도구 업데이트

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

### 5-3. 필요한 패키지를 한 번에 설치

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt`는 설치할 패키지와 버전 범위를 적은 목록입니다. 아래 항목이 함께 설치됩니다. 하위 의존 패키지는 pip가 자동으로 설치하므로 하나씩 따로 설치하지 않아도 됩니다.

| 목록에 적힌 패키지 | 버전 범위 | 하는 일 |
|---|---|---|
| `fastapi` | `>=0.115,<1` | 검색·집계 API와 웹 앱 구성 |
| `uvicorn[standard]` | `>=0.30,<1` | 웹 서버 실행과 개발 중 변경 감지 |
| `httpx` | `>=0.27,<1` | HTTP 요청 도구, 현재는 API 검증에도 사용 |
| `python-dotenv` | `>=1,<2` | `.env`에 적은 DB 설정 읽기 |
| `pymysql[rsa]` | `>=1.1,<2` | Python에서 MySQL 접속, 인증에 필요한 추가 의존성 포함 |
| `pandas` | `>=2.2,<3` | CSV 원자료 읽기와 적재 전처리 |

`[standard]`, `[rsa]`는 추가 기능에 필요한 패키지도 함께 설치한다는 뜻입니다. `cryptography` 등 인증용 의존성도 이 설치 과정에 포함됩니다.

### 5-4. 설치 성공 확인

```powershell
.\.venv\Scripts\python.exe -m pip check
```

`No broken requirements found.`가 나오면 패키지 사이의 의존성 문제를 발견하지 않았다는 뜻입니다. 다음으로 주요 패키지가 실제로 열리는지 확인합니다.

```powershell
.\.venv\Scripts\python.exe -c "import fastapi, uvicorn, httpx, dotenv, pymysql, pandas, cryptography; print('패키지 준비 완료')"
```

마지막에 **패키지 준비 완료**가 나오면 6번으로 진행합니다. 설치가 실패했다면 실패 내용을 확인한 뒤 진행하세요.

## 6. DB 접속 정보 설정

앱은 프로젝트 폴더의 **`.env` 파일**에서 DB 접속 정보를 읽습니다. PC가 바뀌면 그 PC의 MySQL 접속 정보를 입력해야 합니다.

### 6-1. 설정 파일 만들기

PowerShell 터미널에서 다음 명령을 실행합니다. 이미 `.env`가 있으면 그대로 둡니다.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

### 6-2. 비밀번호 수정 후 저장

VS Code 왼쪽에서 `.env`를 열어 다음처럼 설정합니다.

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD="MySQL 설치 때 본인이 정한 비밀번호"
DB_NAME=government_ad_db
```

위의 **MySQL 설치 때 본인이 정한 비밀번호** 부분을 실제 비밀번호로 바꾸고 `Ctrl+S`로 저장합니다. 양쪽 큰따옴표는 유지하세요. 예시 문장을 그대로 비밀번호로 쓰는 것이 아닙니다.

| 항목 | 의미 | 변경하는 경우 |
|---|---|---|
| `DB_HOST` | MySQL이 실행되는 주소 | 같은 PC면 `127.0.0.1` |
| `DB_PORT` | MySQL 접속 포트 | 설치 때 다른 포트를 정했다면 수정 |
| `DB_USER` | MySQL 사용자 계정 | 다른 계정을 쓴다면 수정 |
| `DB_PASSWORD` | 해당 MySQL 계정의 비밀번호 | 본인 비밀번호 입력 |
| `DB_NAME` | 사용할 DB 이름 | 이 안내에서는 `government_ad_db` 유지 |

파일 이름은 **`.env`**여야 합니다. `.env.txt`로 저장하면 읽지 못합니다. `.env`는 GitHub에 포함되지 않도록 설정돼 있으므로 새 PC에서는 직접 만들어야 합니다.

## 7. 처음 설치할 때 DB·표 생성

**새 PC의 새 DB를 준비하는 단계입니다. 이미 정상 작동하는 기존 PC는 이 절과 8번을 건너뜁니다.**

### 7-1. 준비된 SQL 파일만 열어서 실행

1. MySQL Workbench에서 3번의 로컬 접속을 엽니다.
2. **파일 → SQL 스크립트 열기**로 프로젝트의 **`schema.sql`** 파일을 엽니다. 단축키는 `Ctrl+Shift+O`입니다.
3. 파일 이름이 `schema.sql`인 새 탭인지 확인합니다. 다른 SQL 탭의 기존 명령 아래에 내용을 붙여 넣지 않습니다.
4. 이 탭에서 `Ctrl+Shift+Enter`로 파일 전체를 실행합니다.
5. 아래 실행 결과에 빨간 오류가 없는지 확인합니다. 기존 DB·표가 있다는 안내가 나오면 그 객체는 그대로 둔 것입니다.

이 파일은 없는 DB와 표를 만들며, 새 표에는 **매체구분＋총계 금액을 함께 담은 요약 집계용 인덱스**도 생성합니다. 기존 표가 있으면 그 표의 열 형식·자료·인덱스를 자동으로 바꾸지는 않습니다. 기존 DB에 인덱스만 추가하는 방법은 11-2번을 참고하세요.

> 예전 학습용 SQL에 있던 **`DROP TABLE`은 표와 데이터를 삭제하는 명령**입니다. 조회문을 그 아래에 덧붙여 놓고 전체 실행하면 그 삭제문도 실행될 수 있습니다. 이 프로젝트의 설치용 `schema.sql`과 `sql/add_summary_index.sql`에는 표 삭제 명령을 넣지 않았습니다.

### 7-2. 새 표가 비어 있는지 확인

Workbench에서 **`Ctrl+T`로 새 쿼리 탭**을 만들고, 아래 한 문장만 붙여 넣은 뒤 문장 안에 커서를 놓고 **`Ctrl+Enter`**로 실행합니다.

```sql
SELECT COUNT(*) AS 전체건수
FROM government_ad_db.ad_execution;
```

**처음 만든 DB라면 0건**이 나옵니다. 0보다 큰 값이 나오면 이미 자료가 있는 DB입니다. 이 경우 8번의 CSV 적재를 다시 실행하지 말고 기존 자료를 확인하세요.

### 7-3. 앱에서도 DB 접속 확인

VS Code의 PowerShell 터미널에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -c "from database import get_db; conn = get_db(); print('DB 연결 성공'); conn.close()"
```

**DB 연결 성공**이 나오면 앱과 적재 스크립트도 설정한 DB에 접속할 수 있습니다.

## 8. CSV를 DB에 한 번만 적재

**7-2번에서 0건인 것을 확인한 새 DB에서만 진행합니다.** 이 스크립트는 기존 자료에 추가하는 방식이며, 같은 CSV를 다시 넣으면 중복될 수 있습니다.

### 8-1. 원본 파일 확인

프로젝트의 `data` 폴더에는 다음 5개 CSV와 `load_all_years.py`가 있어야 합니다. CSV 파일 이름을 임의로 바꾸지 마세요.

| CSV 파일 | 저장소에 포함된 자료 행 수 |
|---|---:|
| `2022년도_정부광고집행내역_260930 기준.csv` | 214,108 |
| `2023년도_정부광고집행내역_260930 기준.csv` | 229,821 |
| `2024년도_정부광고집행내역_260930 기준.csv` | 235,442 |
| `2025년도_정부광고집행내역_260930 기준.csv` | 247,144 |
| `2026년도_정부광고집행내역_260930 기준.csv` | 145,518 |
| **합계** | **1,072,033** |

위 숫자는 현재 저장소의 CSV에서 제목 행을 제외하고 센 값입니다. 원자료가 바뀌면 기대 건수도 달라집니다.

### 8-2. 적재 명령 실행 — 최초 한 번

VS Code의 PowerShell 터미널에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe data/load_all_years.py
```

연도별 읽기·전처리·적재 완료 메시지가 나옵니다. 모든 연도의 적재 완료와 마지막 완료 메시지까지 기다리세요. 100만 건 이상을 DB에 넣는 최초 작업이므로 시간이 걸릴 수 있습니다. 이 시간은 이후 웹페이지를 여는 시간과 다릅니다.

**중간에 오류가 나오거나 파일 없음 메시지가 나오면:** 명령을 바로 반복하지 말고 오류 내용과 DB 건수를 확인하세요. 10,000건씩 저장을 확정하므로 실패 전 일부 자료가 이미 남아 있을 수 있습니다. 마지막 완료 문구만 보지 말고 각 연도 결과도 확인해야 합니다.

### 8-3. 건수 대조

MySQL Workbench에서 **새 쿼리 탭**을 열어 아래 문장만 실행합니다.

```sql
SELECT COUNT(*) AS 전체건수
FROM government_ad_db.ad_execution;
```

새 빈 DB에 위 CSV 5개가 한 번씩 전부 들어갔다면 **1,072,033건**이어야 합니다. 숫자가 다르면 다음 조회로 연도별 결과도 대조합니다.

```sql
SELECT 집행연도, COUNT(*) AS 건수
FROM government_ad_db.ad_execution
GROUP BY 집행연도
ORDER BY 집행연도;
```

CSV 적재는 처음 한 번만 하는 준비 작업입니다. **앱을 실행할 때마다 다시 실행하는 명령이 아닙니다.**

## 9. 웹 서버 실행과 접속

### 9-1. 서버 시작

VS Code의 PowerShell 터미널에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

다음과 비슷한 문구가 보이면 앱 서버가 시작된 것입니다. PID 숫자 등은 PC마다 다릅니다.

```text
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```

서버를 실행한 터미널은 명령을 기다리는 상태로 돌아오지 않습니다. **앱이 켜져 있는 정상 상태**입니다. 서버가 실행된 뒤 첫 조회까지 확인해야 DB 접속·데이터 적재도 정상인지 알 수 있습니다.

### 9-2. 브라우저 열기

Chrome·Edge 등 브라우저 주소창에 다음 주소를 입력합니다.

**대시보드:** <http://127.0.0.1:8000>

서버 주소를 여는 것이므로 `app.py`나 HTML 파일을 더블클릭해서 열지 않습니다. `127.0.0.1`은 현재 PC 자신을 뜻합니다.

정상 동작 여부를 다음 순서로 확인합니다.

1. 상단 전체 건수가 0이 아닌지, 새 DB 기준으로 위 기대 건수와 일치하는지 확인합니다.
2. 매체별 요약표·차트와 하단 상세 목록이 표시되는지 확인합니다.
3. 연도 선택·기관명 검색을 해봅니다.
4. 상세 목록 안에서 아래로 스크롤하면 추가 자료가 표시되는지 확인합니다. 처음 목록은 최대 2,500건이므로 전체 건수와 처음 표시한 행 수는 다를 수 있습니다.

API 설명 화면은 <http://127.0.0.1:8000/docs>입니다. 일반 사용자는 대시보드 주소만 열면 됩니다.

차트와 화면 스타일 일부는 외부 CDN에서 가져오므로 인터넷 접속이 필요합니다.

## 10. 다음 날 다시 실행·종료

설치를 마쳤다면 **다음 실행부터는 아래 과정만** 하면 됩니다.

1. MySQL Server가 실행 중인지 확인합니다. Windows 시작 시 실행하는 서비스로 설정했다면 자동으로 켜질 수 있습니다. Workbench를 계속 켜둘 필요는 없습니다.
2. VS Code에서 프로젝트 폴더를 열고 PowerShell 터미널을 엽니다.
3. 서버 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

4. 브라우저에서 <http://127.0.0.1:8000>을 엽니다.

**종료:** 서버가 실행 중인 터미널을 클릭하고 **`Ctrl+C`**를 누릅니다. 종료 후에도 MySQL에 저장한 자료는 남습니다. 브라우저 창만 닫는 것으로 서버가 종료되지는 않습니다.

일상 실행 때 Python·MySQL 재설치, 가상환경 재생성, DB 생성, CSV 적재를 반복하지 않습니다.

## 11. 기존 PC에서 수정본만 업데이트

### 11-1. 프로그램 파일 업데이트

**이미 정상 작동 중인 PC용 절차입니다.**

1. 실행 중인 웹 서버를 `Ctrl+C`로 종료합니다.
2. 현재 작업 폴더를 별도로 복사해 둡니다. 특히 **기존 `.env`는 유지**합니다. DB 자체를 백업하려면 12번의 내보내기도 사용합니다.
3. `main`의 최신 ZIP을 받아 새 폴더에 풉니다.
4. 기존 `.env`만 새 프로젝트의 `app.py` 옆에 복사합니다.
5. 새 폴더를 VS Code로 열고 5번에 따라 가상환경을 만든 뒤 패키지를 설치합니다. 기존 `.venv`를 다른 경로로 복사해서 쓰지 않습니다.
6. 9번의 서버 명령으로 실행합니다. `.env`가 같은 MySQL을 가리키면 이미 저장한 자료를 그대로 조회합니다.

**DB 생성이나 CSV 재적재는 하지 않습니다.** 이 저장소를 업데이트한다고 현재 PC의 MySQL 자료나 인덱스가 자동으로 바뀌지는 않습니다.

Git으로 설치한 사람은 본인의 코드 변경과 `.env`를 보관한 뒤 `main`을 업데이트할 수 있습니다. 충돌이 나면 변경 내용을 확인해야 하므로 초보자에게는 위 ZIP·새 폴더 방식으로 안내합니다.

### 11-2. 기존 DB에 속도 개선 인덱스 추가

새 DB를 최신 `schema.sql`로 만들었다면 이 단계는 이미 포함되어 있습니다. 오늘 작업처럼 이미 `idx_ad_summary_cover`를 추가한 PC도 다시 추가할 필요가 없습니다.

먼저 Workbench에서 **새 쿼리 탭**을 열어 아래 한 문장만 실행합니다.

```sql
SHOW INDEX FROM government_ad_db.ad_execution;
```

`Key_name`에 **`idx_ad_summary_cover`**가 있고, 순서대로 **매체구분과 총계(VAT포함)** 2개 열이 표시되면 준비된 것입니다.

그 이름의 인덱스가 없으면 아래 조회를 새 탭에서 실행해 자료형을 먼저 확인합니다.

```sql
SHOW COLUMNS FROM government_ad_db.ad_execution
WHERE `Field` IN ('매체구분', '총계(VAT포함)');
```

이 저장소에서 안내하는 기존 운영 DB의 조건은 **매체구분 `varchar(50)`, 금액 `decimal`**입니다. 금액의 자릿수는 기존 DB의 `(15,2)`와 새 설치의 `(20,2)`가 다를 수 있지만 모두 숫자형입니다.

조건이 맞으면 **`sql/add_summary_index.sql` 파일 자체를 새 탭으로 열고 전체 실행**합니다. 같은 이름의 인덱스가 있으면 작업을 생략하도록 작성했습니다. 생성이 끝나면 웹페이지를 새로고침합니다.

**매체구분이 `TEXT`이거나 구조가 다르면:** 이 안내의 인덱스 SQL을 바로 적용하거나 자료형을 임의로 바꾸지 말고 현재 구조를 확인해야 합니다. `schema.sql`을 다시 실행해도 기존 표의 자료형은 바뀌지 않습니다.

### 11-3. 로딩 진단 로그 읽기

브라우저를 새로고침하면 서버 터미널에 다음 항목이 자동 표시됩니다.

| 로그 항목 | 측정하는 내용 |
|---|---|
| 상단 요약 DB 연결 | MySQL 접속 소요 시간 |
| 상단 요약 전체 집계 | 전체 자료의 매체별 건수·금액 계산과 결과 수신 |
| 상단 요약 서버 처리 | 상단 요약 API 함수의 전체 처리 시간 |
| 선택 목록 서버 처리 | 연도·기관·매체 선택 항목 조회 |
| 세부 데이터 서버 처리 | 상세 목록 API 함수의 처리 시간 |

이 수치는 브라우저의 다운로드·화면 표시까지 모두 포함하는 최종 체감 시간은 아닙니다. 2026-10-19 사용자 PC에서 요약 집계는 변경 전 **11.978초**, 인덱스 추가와 CSV 재적재 후 **0.786초**로 기록됐습니다. 다른 PC의 동일 시간까지 보장하는 수치는 아닙니다.

## 12. 다른 PC로 옮기기·DB 백업

### 방법 A: GitHub의 CSV로 처음 설치

새 PC에서 **1~9번**을 진행합니다. 새 `schema.sql`에는 요약 집계용 인덱스가 포함되어 있습니다. Python·MySQL 설치와 새 PC의 `.env` 입력이 필요합니다.

### 방법 B: 현재 정상 작동하는 DB를 백업해서 복원

이 방법은 지금 DB의 자료·표 구조·인덱스를 함께 옮깁니다. 기존 PC에서 만든 백업을 **새 PC의 새 빈 DB에** 복원하는 절차입니다.

**기존 PC에서 내보내기:**

1. Workbench에서 **Server → Data Export**로 데이터 내보내기 화면을 엽니다.
2. `government_ad_db`와 `ad_execution`을 선택합니다.
3. **구조와 데이터를 모두 포함**하는 내보내기 방식을 선택합니다.
4. **Export to Self-Contained File**로 단일 SQL 파일을 선택하고 저장 위치를 정합니다.
5. 내보내기 시작 후 성공 여부와 생성된 파일을 확인합니다.
6. 생성된 백업 파일을 새 PC로 옮깁니다.

**새 PC에서 가져오기:**

1. Python·MySQL·프로젝트·패키지를 준비하고 새 PC의 `.env`를 설정합니다.
2. Workbench에서 **새 PC의 로컬 MySQL**에 접속했는지 확인합니다.
3. **Server → Data Import**로 데이터 가져오기 화면을 엽니다.
4. **Import from Self-Contained File**로 위 SQL 백업 파일을 선택합니다.
5. 가져올 대상은 **새 빈 `government_ad_db`**로 지정합니다. 대상 DB가 없으면 이 화면의 새 DB 만들기 기능으로 생성합니다.
6. 가져오기 성공 후 전체 건수와 `idx_ad_summary_cover`를 확인합니다.
7. 9번의 앱 실행 명령으로 시작합니다.

**DB 백업 복원과 CSV 적재 중 하나만 선택합니다.** DB를 복원한 뒤 같은 CSV까지 다시 넣으면 중복될 수 있습니다. 백업은 기존 자료를 덮어쓸 수 있는 SQL을 포함할 수 있으므로, 이미 자료가 있는 DB에 테스트 삼아 가져오지 않습니다. 접속 비밀번호는 백업을 받는 새 PC에 맞게 `.env`에 설정합니다.

## 13. 오류가 나거나 자료가 안 보일 때

오류창의 내용을 모르면 무시나 재시도를 반복하지 말고, 오류 문구와 어떤 단계에서 실행했는지부터 기록하세요. `.env`나 비밀번호를 다른 사람에게 보낼 때는 비밀번호를 가립니다.

| 증상·문구 | 확인할 내용과 조치 |
|---|---|
| `py`를 찾을 수 없음 | Python 설치를 확인하고 터미널을 다시 엽니다. Python 3.13이 설치되어 `python --version`으로 확인되면 `python -m venv .venv`로 생성할 수 있습니다. 다른 버전이 나오면 설치된 3.13 실행 도구를 먼저 확인합니다. |
| `.venv\Scripts\python.exe`를 찾을 수 없음 | 현재 폴더에 `app.py`가 있는지, 5-1번으로 `.venv`를 만들었는지 확인합니다. |
| `requirements.txt`가 없음 | 압축을 풀었는지, VS Code에서 `app.py`가 있는 프로젝트 폴더를 열었는지 확인합니다. |
| `ModuleNotFoundError` | 5-3번 패키지 설치를 하고 앱 실행에도 같은 `.venv`의 Python 경로를 사용합니다. |
| PowerShell에서 스크립트 실행이 차단됨 | 활성화 스크립트 대신 이 문서의 `.venv\Scripts\python.exe` 명령을 직접 사용합니다. |
| MySQL 접속 거부·연결 실패, `2003` | Windows 서비스에서 MySQL Server가 실행 중인지, `.env`의 주소·포트가 Workbench 접속과 같은지 확인합니다. |
| `Access denied`, `1045` | `.env`의 사용자·비밀번호가 그 MySQL 접속과 일치하는지 확인하고 저장합니다. 수정 후 앱 서버를 다시 시작합니다. |
| `cryptography`가 필요하다는 오류 | 최신 `requirements.txt`로 5-3번을 실행합니다. `pymysql[rsa]`가 인증용 의존성을 함께 설치합니다. |
| `Unknown database`, `1049` | 처음 설치라면 7번을 진행합니다. 기존 PC라면 DB 이름·접속 서버를 확인합니다. |
| 표를 찾을 수 없음, `1146` | 올바른 MySQL과 DB인지 확인하고 처음 설치라면 `schema.sql` 실행 결과를 확인합니다. |
| CSV 파일 없음 | `data` 폴더의 5개 파일과 이름을 8-1번 표와 대조합니다. 일부만 적재됐다면 전체 명령을 반복하지 않습니다. |
| 화면 전체 0건 | 새 Workbench 탭에서 7-2번의 `COUNT(*)` 조회로 실제 건수를 확인합니다. 연결 정보·적재 결과·SQL 실행 기록을 확인한 뒤 조치합니다. |
| 기대 건수보다 많음 | 중복 적재 가능성을 확인합니다. 임의로 표를 지우거나 같은 CSV를 다시 넣지 않습니다. |
| 서버는 켜지지만 DB 오류가 남 | 시작 문구만으로 DB 연결이 검증되지는 않습니다. 7-3번 접속 검사와 서버 터미널의 오류를 확인합니다. |
| 요약만 오래 걸림 | 11-2번 인덱스 확인과 11-3번 진단 시간을 확인합니다. 상세 목록의 2,500건 제한은 상단 전체 집계량을 제한하지 않습니다. |
| `8000` 포트를 이미 사용 중 | 다른 터미널의 서버가 켜져 있는지 확인해 종료합니다. 또는 아래의 `8001` 예시로 실행합니다. |
| 차트·스타일만 안 보임 | 외부 CDN 접속이 가능한지 확인합니다. 서버 API 오류는 별도로 터미널에서 확인합니다. |

다른 포트로 실행할 때는 다음 명령을 사용하고, 브라우저도 <http://127.0.0.1:8001>로 엽니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8001
```

**실행 기록의 날짜 확인:** Workbench 하단 출력 종류를 **History Output**으로 바꾸고 날짜를 선택한 뒤 시간 항목을 클릭합니다. Action Output의 시·분·초만 보고 같은 날짜의 실행이라고 판단하지 않습니다.

## 14. 공식 설치 문서

설치 화면과 배포 버전은 바뀔 수 있습니다. 이 안내에서 사용하는 제품·명령의 원문은 다음 공식 문서에서 확인할 수 있습니다.

- [Python Windows 다운로드](https://www.python.org/downloads/windows/) · [Windows 설치 안내](https://docs.python.org/3.13/using/windows.html)
- [Python 가상환경과 직접 실행](https://docs.python.org/3/library/venv.html)
- [VS Code Windows 설치](https://code.visualstudio.com/docs/setup/windows)
- [MySQL Installer 다운로드](https://dev.mysql.com/downloads/installer/) · [제품 선택](https://dev.mysql.com/doc/mysql-installer/en/mysql-installer-setup.html) · [서버 설정](https://dev.mysql.com/doc/mysql-installer/en/mysql-installer-workflow-server.html)
- [Workbench SQL 실행 단축키](https://dev.mysql.com/doc/workbench/en/wb-keys.html) · [실행 기록](https://dev.mysql.com/doc/workbench/en/wb-develop-sql-editor-history.html)
- [Workbench DB 내보내기·가져오기](https://dev.mysql.com/doc/workbench/en/wb-admin-export-import-management.html)
- [PyMySQL 설치와 인증용 추가 의존성](https://github.com/PyMySQL/PyMySQL#installation)
- [MySQL 인덱스 사용 원리](https://dev.mysql.com/doc/refman/8.0/en/mysql-indexes.html)
