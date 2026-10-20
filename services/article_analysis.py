"""연도 조합별 기간 규칙과 원자료 집계. 기존 대시보드 조회와 분리한다."""

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from media_analysis import comparison, run_analysis as core
from media_analysis.write_article import build_article_analysis

YEARS = tuple(range(2022, 2027))


def pair_settings(base_year, current_year):
    if base_year not in YEARS or current_year not in YEARS or base_year == current_year:
        raise ValueError("2022~2026년 중 서로 다른 두 연도를 선택하세요.")
    settings = core.load_settings()
    settings.update(year=str(base_year), compare_year=str(current_year), period_policy="year_pair", source="csv", start_on_or_after=None)
    settings["start_on_or_before"] = f"{base_year}-09-30" if 2026 in (base_year, current_year) else None
    return settings


def available_years():
    return [year for year in YEARS if (core.PROJECT_DIR / "data" / f"{year}년도_정부광고집행내역_260930 기준.csv").is_file()]


@lru_cache(maxsize=12)
def _period(path_text, modified_ns, size, settings_json, groups_json):
    # 수정 시각·크기·분류·설정을 키로 삼아 같은 자료를 조합마다 다시 읽지 않는다.
    path = Path(path_text)
    groups = json.loads(groups_json)
    lookup = {core.normalize_name(alias): brand for brand in groups["brands"] for alias in brand["aliases"]}
    settings = json.loads(settings_json)
    source = {"mode": "CSV 원자료", "file_name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "provider": "한국언론진흥재단(프로젝트에 저장된 원자료)", "reference_date": "2026-09-30"}
    facts, _, _ = core.aggregate(core.csv_rows(path), settings, groups, lookup, source)
    if path.stat().st_mtime_ns != modified_ns or path.stat().st_size != size:
        raise ValueError("집계 중 원자료가 변경됐습니다. 근거를 다시 불러오세요.")
    return facts


def prepare_pair(base_year, current_year):
    settings = pair_settings(base_year, current_year)
    groups, _ = core.load_groups()
    periods = []
    for year in (base_year, current_year):
        path = core.PROJECT_DIR / "data" / f"{year}년도_정부광고집행내역_260930 기준.csv"
        if not path.is_file():
            raise ValueError(f"{year}년 원자료 CSV가 없습니다.")
        stat = path.stat()
        period = comparison.period_settings(settings, year)
        for key in ("compare_year", "output_folder", "openai_model"):
            period.pop(key, None)
        periods.append(copy.deepcopy(_period(str(path), stat.st_mtime_ns, stat.st_size, json.dumps(period, sort_keys=True), json.dumps(groups, sort_keys=True))))
    fact = comparison.build_comparison(*periods, settings)
    fact["scope"]["period_label"] = "양쪽 광고시작일 각각 9월 30일 이하" if 2026 in (base_year, current_year) else "각 연도 원자료 전체 · 연간 비교"
    # 기관별 부분 집계가 전체 합계와 일치하는지 유료 호출 전에 검사한다.
    fact["기사용분석"] = build_article_analysis(fact)
    return {"settings": settings, "fact_sheet": fact}
