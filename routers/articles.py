"""웹 기사 생성·검수·승인 API. 광고 원자료에는 쓰기 작업을 하지 않는다."""

import logging
import os
from functools import wraps
from typing import Annotated

import pymysql
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from media_analysis import run_analysis as core
from media_analysis.write_article import generate_fact
from services.article_analysis import YEARS, available_years, prepare_pair
from services.article_repository import ArticleError, ArticleRepository

router = APIRouter(prefix="/api/articles", tags=["기사 작성·검수"])
repository = ArticleRepository()
logger = logging.getLogger("uvicorn.error")
Year = Annotated[int, Field(strict=True, ge=2022, le=2026)]
Revision = Annotated[int, Field(strict=True, ge=1)]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PrepareRequest(Request):
    base_years: list[Year] = Field(min_length=1, max_length=5)
    compare_years: list[Year] = Field(min_length=1, max_length=5)


class ContentRequest(Request):
    revision: Revision
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=100000)


class Checks(Request):
    numbers: StrictBool
    scope: StrictBool
    claims: StrictBool
    sources: StrictBool


class ReviewRequest(Request):
    revision: Revision
    reviewer: str = Field(min_length=1, max_length=80)
    checks: Checks
    comment: str = Field(default="", max_length=5000)


class ApproveRequest(Request):
    revision: Revision


def api_errors(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except ArticleError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        except pymysql.MySQLError as exc:
            raise HTTPException(503, "기사 DB에 연결할 수 없거나 표가 없습니다. DB 접속 설정과 sql/create_article_review_tables.sql 실행 여부를 확인하세요.") from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc
    return wrapped


@router.get("/config")
def config():
    try:
        repository.ready()
        ready, error = True, ""
    except pymysql.MySQLError:
        ready, error = False, "MySQL 접속 설정을 확인하고 sql/create_article_review_tables.sql을 실행하세요."
    settings = core.load_settings()
    groups, _ = core.load_groups()
    return {"years": list(YEARS), "available_years": available_years(), "model": settings.get("openai_model", "gpt-4.1-mini"), "api_key_ready": bool(os.getenv("OPENAI_API_KEY", "").strip()), "db_ready": ready, "db_error": error, "brands": groups["brands"], "org_types": settings["org_types"], "media_types": settings["media_types"]}


@router.get("")
@api_errors
def list_articles():
    return {"articles": repository.list()}


@router.get("/published")
@api_errors
def published_articles():
    return {"articles": repository.list(approved_only=True)}


@router.post("/prepare", status_code=201)
@api_errors
def prepare_articles(request: PrepareRequest):
    repository.ready()  # DB가 준비되지 않았다면 무거운 CSV 집계부터 실행하지 않는다.
    pairs = [(base, current) for base in sorted(set(request.base_years)) for current in sorted(set(request.compare_years)) if base != current]
    if not pairs:
        raise ArticleError(400, "서로 다른 기준연도와 비교연도를 선택하세요.")
    prepared = [prepare_pair(base, current) for base, current in pairs]
    ids = repository.create_many(prepared)
    return {"article_ids": ids, "pairs": [{"id": article_id, "base_year": base, "current_year": current} for article_id, (base, current) in zip(ids, pairs)]}


@router.get("/{article_id}")
@api_errors
def get_article(article_id: int):
    return repository.get(article_id)


@router.post("/{article_id}/generate")
@api_errors
def generate_article(article_id: int):
    article = repository.get(article_id)
    if article["generation_status"] == "완료":
        return article
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ArticleError(503, ".env에 OPENAI_API_KEY를 입력하고 서버를 재시작하세요.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ArticleError(503, "기사 작성 패키지를 설치하세요: python -m pip install -r requirements.txt") from exc
    token = repository.reserve_generation(article_id)
    if token is None:
        return repository.get(article_id)
    try:
        text, record = generate_fact(article["fact_sheet"], article["settings_json"], key, OpenAI)
        lines = text.splitlines()
        title = lines[0].strip().removeprefix("제목:").strip().lstrip("# ").strip("*").strip()
        body = "\n".join(lines[1:]).strip()
        if not title or not body or len(title) > 300:
            raise ValueError("제목과 본문이 구분된 완성된 기사 응답이 필요합니다.")
        repository.finish_generation(article_id, token, title, body, record)
    except Exception as exc:
        # 외부 예외 메시지에는 인증 정보가 들어갈 수 있으므로 코드만 기록한다.
        if isinstance(exc, (ValueError, ArticleError)):
            message = str(exc)
        else:
            code = getattr(exc, "status_code", None)
            message = f"기사 생성에 실패했습니다({code or type(exc).__name__}). API 키·잔액·연결 상태를 확인하세요."
        repository.fail_generation(article_id, token, message)
        raise ArticleError(502, message) from exc
    return repository.get(article_id)


@router.put("/{article_id}")
@api_errors
def update_article(article_id: int, request: ContentRequest):
    repository.save_content(article_id, request.revision, request.title, request.body)
    return repository.get(article_id)


@router.put("/{article_id}/review")
@api_errors
def review_article(article_id: int, request: ReviewRequest):
    repository.review(article_id, request.revision, request.reviewer, request.checks.model_dump(), request.comment)
    return repository.get(article_id)


@router.put("/{article_id}/hold")
@api_errors
def hold_article(article_id: int, request: ReviewRequest):
    repository.review(article_id, request.revision, request.reviewer, request.checks.model_dump(), request.comment, hold=True)
    return repository.get(article_id)


@router.put("/{article_id}/approve")
@api_errors
def approve_article(article_id: int, request: ApproveRequest):
    repository.approve(article_id, request.revision)
    return repository.get(article_id)
