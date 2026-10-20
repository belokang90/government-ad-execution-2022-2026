"""앱 시작점: 화면·정적 파일·정부광고 API를 연결한다."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from config import BASE_DIR
from routers.ads import router as ads_router
from routers.articles import router as articles_router

app = FastAPI(title="정부광고 집행내역 (2022~2026.09.30 기준)")
# 2,500건 JSON을 압축해 전송량을 줄인다. 데이터와 응답 구조는 유지한다.
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(ads_router)
app.include_router(articles_router)


@app.get("/", response_class=FileResponse, include_in_schema=False)
def home():
    """정부광고 집행내역 HTML을 보낸다. CSS·JS는 /static 경로에서 불러온다."""
    return FileResponse(BASE_DIR / "templates" / "index.html", media_type="text/html")


@app.get("/articles", response_class=FileResponse, include_in_schema=False)
def article_editor():
    return FileResponse(BASE_DIR / "templates" / "articles.html", media_type="text/html")


@app.get("/articles/published", response_class=FileResponse, include_in_schema=False)
def published_articles():
    return FileResponse(BASE_DIR / "templates" / "published_articles.html", media_type="text/html")
