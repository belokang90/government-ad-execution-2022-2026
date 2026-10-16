"""앱 시작점: 화면·정적 파일·정부광고 API를 연결한다."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import BASE_DIR
from routers.ads import router as ads_router

app = FastAPI(title="정부광고 집행내역 대시보드")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(ads_router)


@app.get("/", response_class=FileResponse, include_in_schema=False)
def home():
    """대시보드 HTML을 보낸다. CSS·JS는 /static 경로에서 불러온다."""
    return FileResponse(BASE_DIR / "templates" / "index.html", media_type="text/html")
