"""같은 기관·매체·날짜 조건으로 두 연도를 함께 집계하고 증감을 계산한다."""

import hashlib
import html
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

if __package__:
    from . import run_analysis as core
else:
    import run_analysis as core


def period_settings(settings, year):
    result = dict(settings, year=str(year))
    if settings.get("period_policy") == "year_pair":
        partial = "2026" in (str(settings["year"]), str(settings["compare_year"]))
        result["start_on_or_before"] = f"{year}-09-30" if partial else None
        result["start_on_or_after"] = None
        return result
    result["start_on_or_before"] = date.fromisoformat(settings["start_on_or_before"]).replace(year=int(year)).isoformat() if settings.get("start_on_or_before") else None
    if settings.get("start_on_or_after"):
        result["start_on_or_after"] = date.fromisoformat(settings["start_on_or_after"]).replace(year=int(year)).isoformat()
    return result


def percentage_change(base, current):
    return core.amount_text(((current-base)/base*100).quantize(Decimal("0.01"))) if base else None


def compare_values(base, current, base_denominator, current_denominator):
    base_amount = core.money(base.get("total_amount", "0"))
    current_amount = core.money(current.get("total_amount", "0"))
    base_count, current_count = base.get("ad_count", 0), current.get("ad_count", 0)
    base_share = base_amount/base_denominator*100 if base_denominator else None
    current_share = current_amount/current_denominator*100 if current_denominator else None
    return {
        "base_count": base_count, "current_count": current_count,
        "count_change": current_count-base_count,
        "count_change_pct": percentage_change(Decimal(base_count), Decimal(current_count)),
        "base_amount": core.amount_text(base_amount), "current_amount": core.amount_text(current_amount),
        "amount_change": core.amount_text(current_amount-base_amount),
        "amount_change_pct": percentage_change(base_amount, current_amount),
        "base_share_pct": core.amount_text(base_share.quantize(Decimal("0.0001"))) if base_share is not None else None,
        "current_share_pct": core.amount_text(current_share.quantize(Decimal("0.0001"))) if current_share is not None else None,
        "share_change_pp": core.amount_text((current_share-base_share).quantize(Decimal("0.0001"))) if base_share is not None and current_share is not None else None,
        "direction": "증가" if current_amount>base_amount else "감소" if current_amount<base_amount else "동일",
        "rate_note": "기준연도 금액이 0원이므로 증감률 계산 불가" if not base_amount else "",
    }


def build_comparison(base, current, settings):
    if base["brand_definitions"] != current["brand_definitions"]:
        raise ValueError("두 연도의 매체 분류 기준이 다릅니다.")
    base_year, current_year = str(settings["year"]), str(settings["compare_year"])
    base_denominator = core.money(base["eligible_total"]["total_amount"])
    current_denominator = core.money(current["eligible_total"]["total_amount"])
    result = {
        "schema": "media_comparison_v1",
        "topic": f"{base_year}년 대비 {current_year}년 대표 매체군 정부광고 비교",
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        "scope": {**settings, "base_year": base_year, "current_year": current_year,
                  "base_cutoff": base["scope"]["start_on_or_before"], "current_cutoff": current["scope"]["start_on_or_before"],
                  "date_field": "광고시작일", "amount_unit": "원(VAT 포함)", "count_unit": "원자료 행 수",
                  "denominator": "각 연도에서 같은 기관·시작일 조건을 충족한 모든 매체구분의 광고비"},
        "classification_note": base["classification_note"],
        "classification_sources": base["classification_sources"], "brand_definitions": base["brand_definitions"],
        "limitations": base["limitations"] + [f"증감은 비교연도에서 기준연도를 뺀 값이다. {base_year}년과 {current_year}년의 두 연도 간 비교다.", "기준연도가 0원이면 증감률을 100%나 0%로 대체하지 않고 계산 불가로 표시한다."],
        "periods": {base_year: base, current_year: current},
        "all_media_comparison": compare_values(base["eligible_total"], current["eligible_total"], base_denominator, current_denominator),
        "selected_comparison": compare_values(base["selected_total"], current["selected_total"], base_denominator, current_denominator),
    }
    for field, key in (("groups", "group"), ("statistics", "brand")):
        left = {item[key]: item for item in base[field]}
        right = {item[key]: item for item in current[field]}
        result[field] = []
        for name, item in left.items():
            comparison = compare_values(item, right.get(name, {}), base_denominator, current_denominator)
            comparison.update({key: name, "group": item["group"]})
            result[field].append(comparison)
    dimensions = ("group", "brand", "org_type", "media_type")
    left = {tuple(item[k] for k in dimensions): item for item in base["breakdown"]}
    right = {tuple(item[k] for k in dimensions): item for item in current["breakdown"]}
    result["breakdown"] = [{**dict(zip(dimensions, key)), **compare_values(left.get(key, {}), right.get(key, {}), base_denominator, current_denominator)} for key in sorted(left.keys()|right.keys())]
    result["registered_names"] = [{"year": year, **row} for year, period in result["periods"].items() for row in period["registered_names"]]
    result["review_candidates"] = [{"year": year, **row} for year, period in result["periods"].items() for row in period["review_candidates"]]
    return result


COMPARISON_FIELDS = ["group", "brand", "base_count", "current_count", "count_change", "count_change_pct", "base_amount", "current_amount", "amount_change", "amount_change_pct", "base_share_pct", "current_share_pct", "share_change_pp", "direction", "rate_note"]


def write_outputs(folder, fact, details, invalid_dates):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"fact_sheet.json").write_text(json.dumps(fact, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = {"fact_sheet": fact, "records": details}
    (folder/"report_data.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    core.write_csv(folder/"all_ads.csv", ["자료연도"]+core.DETAIL_FIELDS, details)
    for year in fact["periods"]:
        core.write_csv(folder/f"all_ads_{year}.csv", ["자료연도"]+core.DETAIL_FIELDS, [row for row in details if row["자료연도"]==year])
    core.write_csv(folder/"comparison_summary.csv", COMPARISON_FIELDS, fact["statistics"])
    core.write_csv(folder/"group_comparison.csv", COMPARISON_FIELDS, fact["groups"])
    core.write_csv(folder/"registered_names.csv", ["year", "group", "brand", "raw_media_name", "media_type", "ad_count", "total_amount"], fact["registered_names"])
    core.write_csv(folder/"review_candidates.csv", ["year", "raw_media_name", "media_type", "ad_count", "total_amount", "reason"], fact["review_candidates"])
    core.write_csv(folder/"invalid_start_dates.csv", ["자료연도", "원자료참조"]+core.RAW_FIELDS, invalid_dates)
    template = (core.BASE_DIR/"report_template.html").read_text(encoding="utf-8")
    content = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = template.replace("__BASE_YEAR__", fact["scope"]["base_year"]).replace("__CURRENT_YEAR__", fact["scope"]["current_year"])
    (folder/"report.html").write_text(template.replace("__REPORT_DATA__", content).replace("__REPORT_TITLE__", html.escape(fact["topic"])), encoding="utf-8")


def collect(settings, groups, lookup, source_type, base_csv=None, current_csv=None):
    if source_type not in ("csv", "mysql"):
        raise ValueError("자료 종류는 csv 또는 mysql이어야 합니다.")
    periods, details, invalid_dates = {}, [], []
    for index, year in enumerate((str(settings["year"]), str(settings["compare_year"]))):
        period = period_settings(settings, year)
        if source_type == "csv":
            custom = base_csv if index==0 else current_csv
            path = custom or core.PROJECT_DIR/"data"/f"{year}년도_정부광고집행내역_260930 기준.csv"
            if not path.is_file():
                raise ValueError(f"{year}년 원자료가 없습니다: {path.name}")
            source = {"mode": "CSV 원자료", "file_name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "provider": "한국언론진흥재단(프로젝트에 저장된 원자료)", "reference_date": "2026-09-30"}
            rows = core.csv_rows(path)
        else:
            source = {"mode": "기존 MySQL 읽기 전용 조회", "table": "ad_execution", "year_field": "집행연도", "provider": "기존 정부광고 DB", "reference_date": "DB에 적재된 자료 기준"}
            rows = core.mysql_rows(period)
        print(f"{year}년 자료를 집계합니다...")
        try:
            facts, selected, invalid = core.aggregate(rows, period, groups, lookup, source)
        finally:
            close = getattr(rows, "close", None)
            if close:
                close()
        periods[year] = facts
        details.extend({"자료연도": year, **row} for row in selected)
        invalid_dates.extend({"자료연도": year, **row} for row in invalid)
    base_year, current_year = str(settings["year"]), str(settings["compare_year"])
    fact = build_comparison(periods[base_year], periods[current_year], settings)
    fact["scope"]["period_label"] = "양쪽 광고시작일 각각 9월 30일 이하" if fact["scope"]["base_cutoff"] else "각 연도 원자료 전체 · 연간 비교"
    return fact, details, invalid_dates


def execute(settings, args, groups, lookup, source_type):
    fact, details, invalid_dates = collect(settings, groups, lookup, source_type, args.csv, args.compare_csv)
    base_year, current_year = str(settings["year"]), str(settings["compare_year"])
    folder = args.output or core.BASE_DIR/settings.get("output_folder", "comparison_output")
    write_outputs(folder, fact, details, invalid_dates)
    print(f"{base_year}년 대비 {current_year}년 비교 완료. 양쪽 광고 내역 전체 {len(details):,}행")
    for row in fact["groups"]:
        pct = f"{row['amount_change_pct']}%" if row["amount_change_pct"] is not None else "계산 불가"
        print(f"{row['group']}: {core.money(row['base_amount']):,.0f}원 -> {core.money(row['current_amount']):,.0f}원 / {row['direction']} {pct}")
    print(f"비교 화면: {folder/'report.html'}")
    print("기사 생성은 WRITE_ARTICLE.bat을 실행하세요.")
    if args.open_report:
        import webbrowser
        webbrowser.open((folder/"report.html").resolve().as_uri())
