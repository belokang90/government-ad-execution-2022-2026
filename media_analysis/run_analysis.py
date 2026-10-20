"""기존 CSV 또는 MySQL을 읽어 전체 내역, 집계, 팩트시트, HTML을 만든다.

실행: python media_analysis/run_analysis.py
MySQL 사용: python media_analysis/run_analysis.py --source mysql
DB에는 SELECT만 실행하며, 원자료와 기존 fact_sheet.json은 변경하지 않는다.
"""

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
RAW_FIELDS = ["기관분류", "기관명", "매체구분", "매체명", "광고명", "광고료", "수수료", "총계(VAT포함)", "광고시작일", "광고종료일"]
DETAIL_FIELDS = ["분석매체군", "통합매체명", "원자료참조", "이전연도시작", "분석시작일"] + RAW_FIELDS
LIMITATION = "해당 연도 파일에서 광고시작일로 추린 결과다. 수탁일자·지급일자 기준의 1~9월 실제 지출액이 아니며, 여러 달에 걸친 광고금액을 기간별로 나누지 않았다. 건수는 원자료 행 수이고 고유 캠페인 수가 아니다."


def normalize_name(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def money(value):
    text = str(value if value is not None else "").strip().replace(",", "")
    if not text:
        raise ValueError("총계(VAT포함) 금액이 누락되었습니다. 원자료를 확인하세요.")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"금액을 읽을 수 없습니다: {text!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"유효하지 않은 금액입니다: {text!r}")
    return amount


def amount_text(value):
    return format(value, "f")


def parse_start(value):
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}\.0", text):
        text = text[:-2]
    for pattern in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


def load_settings(path=BASE_DIR / "settings.json"):
    settings = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    year = int(settings["year"])
    cutoff = date.fromisoformat(settings["start_on_or_before"]) if settings.get("start_on_or_before") else None
    lower = settings.get("start_on_or_after")
    if settings.get("period_policy") != "year_pair" and ((cutoff and cutoff.year != year) or (lower and cutoff and date.fromisoformat(lower) > cutoff)):
        raise ValueError("연도와 광고시작일 범위를 확인하세요.")
    if not settings.get("org_types") or not settings.get("media_types"):
        raise ValueError("기관분류와 매체구분은 하나 이상 지정해야 합니다.")
    if settings.get("compare_year"):
        compare_year = int(settings["compare_year"])
        if compare_year == year:
            raise ValueError("비교연도는 기준연도와 달라야 합니다.")
        if cutoff:
            cutoff.replace(year=compare_year)
    return settings


def load_groups(path=BASE_DIR / "media_groups.json"):
    groups = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    lookup = {}
    seen_brands = set()
    for brand in groups["brands"]:
        if brand["brand"] in seen_brands:
            raise ValueError("통합매체명이 중복되었습니다.")
        seen_brands.add(brand["brand"])
        for alias in brand["aliases"]:
            key = normalize_name(alias)
            if not key or (key in lookup and lookup[key]["brand"] != brand["brand"]):
                raise ValueError(f"매체명 연결이 충돌합니다: {alias}")
            lookup[key] = brand
    return groups, lookup


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(RAW_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV에 필요한 항목이 없습니다: {sorted(missing)}")
        for line, row in enumerate(reader, 2):
            yield row, f"CSV:{line}행"


def mysql_rows(settings):
    sys.path.insert(0, str(PROJECT_DIR))
    from database import get_db
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(settings["org_types"]))
            columns = ",".join(f"`{field}`" for field in RAW_FIELDS)
            sql = f"SELECT {columns} FROM ad_execution WHERE `집행연도`=%s AND `기관분류` IN ({placeholders})"
            cursor.execute(sql, (str(settings["year"]), *settings["org_types"]))
            number = 0
            while True:
                batch = cursor.fetchmany(5000)
                if not batch:
                    break
                for row in batch:
                    number += 1
                    yield row, f"MySQL조회:{number}행"
    finally:
        connection.close()


def aggregate(rows, settings, groups, lookup, source):
    cutoff = date.fromisoformat(settings["start_on_or_before"]) if settings.get("start_on_or_before") else None
    lower = date.fromisoformat(settings["start_on_or_after"]) if settings.get("start_on_or_after") else None
    year = int(settings["year"])
    audit = Counter()
    eligible_amount = Decimal("0")
    eligible_by_org = defaultdict(lambda: [0, Decimal("0")])
    brand_totals = {item["brand"]: {"group": item["group"], "brand": item["brand"], "ad_count": 0, "total_amount": Decimal("0"), "previous_year_start_count": 0, "raw_media_names": set()} for item in groups["brands"]}
    breakdown = defaultdict(lambda: [0, Decimal("0")])
    aliases = defaultdict(lambda: [0, Decimal("0")])
    review = defaultdict(lambda: [0, Decimal("0")])
    details, invalid_dates = [], []
    duplicate_keys = Counter()
    selected_amount = Decimal("0")
    review_terms = [normalize_name(term) for term in groups.get("review_terms", [])]

    for raw, reference in rows:
        audit["read_rows"] += 1
        row = {field: "" if raw.get(field) is None else str(raw[field]) for field in RAW_FIELDS}
        if row["기관분류"] not in settings["org_types"]:
            audit["excluded_org_rows"] += 1
            continue
        start = parse_start(raw.get("광고시작일"))
        if start is None:
            audit["invalid_start_date_rows"] += 1
            invalid_dates.append({"원자료참조": reference, **row})
            if cutoff or lower:
                continue
        if start and ((cutoff and start > cutoff) or (lower and start < lower)):
            audit["excluded_date_rows"] += 1
            continue
        amount = money(row["총계(VAT포함)"])
        audit["eligible_rows"] += 1
        eligible_amount += amount
        eligible_by_org[row["기관분류"]][0] += 1
        eligible_by_org[row["기관분류"]][1] += amount
        brand = lookup.get(normalize_name(row["매체명"]))
        if brand and row["매체구분"] in settings["media_types"]:
            audit["selected_rows"] += 1
            previous_year = bool(start and start.year < year)
            audit["selected_previous_year_start_rows"] += int(previous_year)
            selected_amount += amount
            item = brand_totals[brand["brand"]]
            item["ad_count"] += 1
            item["total_amount"] += amount
            item["previous_year_start_count"] += int(previous_year)
            item["raw_media_names"].add(row["매체명"])
            key = (brand["group"], brand["brand"], row["기관분류"], row["매체구분"])
            breakdown[key][0] += 1
            breakdown[key][1] += amount
            aliases[(brand["group"], brand["brand"], row["매체명"], row["매체구분"])][0] += 1
            aliases[(brand["group"], brand["brand"], row["매체명"], row["매체구분"])][1] += amount
            details.append({"분석매체군": brand["group"], "통합매체명": brand["brand"], "원자료참조": reference, "이전연도시작": "확인 불가" if start is None else "예" if previous_year else "아니오", "분석시작일": start.isoformat() if start else "", **row})
            duplicate_keys[tuple(row[field] for field in RAW_FIELDS)] += 1
        else:
            audit["unclassified_rows"] += 1
            name_key = normalize_name(row["매체명"])
            if any(term in name_key for term in review_terms):
                reason = "매체구분 제외" if brand else "정확 일치 목록에 없음. 계열·대행·동명이체 여부 검토"
                review[(row["매체명"], row["매체구분"], reason)][0] += 1
                review[(row["매체명"], row["매체구분"], reason)][1] += amount

    group_totals = {}
    for item in brand_totals.values():
        group = group_totals.setdefault(item["group"], {"group": item["group"], "ad_count": 0, "total_amount": Decimal("0")})
        group["ad_count"] += item["ad_count"]
        group["total_amount"] += item["total_amount"]
    for item in list(group_totals.values()) + list(brand_totals.values()):
        item["share_of_eligible_amount_pct"] = amount_text((item["total_amount"] / eligible_amount * 100).quantize(Decimal("0.0001"))) if eligible_amount else None
        item["total_amount"] = amount_text(item["total_amount"])
        if "raw_media_names" in item:
            item["raw_media_names"] = sorted(item["raw_media_names"])
    audit["selected_exact_duplicate_extra_rows"] = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    assert audit["eligible_rows"] == audit["selected_rows"] + audit["unclassified_rows"]
    assert sum(item["ad_count"] for item in brand_totals.values()) == len(details)
    assert sum(money(item["total_amount"]) for item in brand_totals.values()) == selected_amount
    details.sort(key=lambda item: (item["분석매체군"], item["통합매체명"], item["분석시작일"], item["기관명"], item["광고명"], item["원자료참조"]))

    fact_sheet = {
        "topic": f"{year}년 자료의 광고시작일 {cutoff.isoformat()} 이하 대표 매체군 정부광고" if cutoff else f"{year}년 연간 원자료 전체의 대표 매체군 정부광고",
        "source": source,
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
        "scope": {**settings, "date_field": "광고시작일", "previous_year_starts_included": lower is None, "denominator": "같은 기관·시작일 조건을 충족한 모든 매체구분의 광고금액", "amount_unit": "원(VAT 포함)", "amount_field": "총계(VAT포함)", "count_unit": "원자료 행 수"},
        "classification_note": groups["classification_note"],
        "classification_sources": groups["sources"],
        "brand_definitions": groups["brands"],
        "limitations": [LIMITATION if cutoff or lower else "각 연도 원자료 파일 전체에 기관·매체 조건을 적용한 연간 비교다. 광고시작일로 추가 제외하지 않으며 날짜 미확인 행도 포함한다. 지급일 기준 지출이나 예산총액이 아니고, 금액은 기간별로 나누지 않았다. 건수는 원자료 행 수다.", "예산·매체선정 사유나 특혜·차별의 원인을 이 집계만으로 판단하지 않는다.", "등록명 목록에 없는 다른 언론·계열사·대행 표기는 두 매체군에 포함하지 않았다.", "정확히 같은 행이 있어도 실제 중복 여부를 확정할 수 없어 삭제하지 않았다."],
        "eligible_total": {"ad_count": audit["eligible_rows"], "total_amount": amount_text(eligible_amount)},
        "selected_total": {"ad_count": len(details), "total_amount": amount_text(selected_amount)},
        "unclassified_total": {"ad_count": audit["unclassified_rows"], "total_amount": amount_text(eligible_amount - selected_amount)},
        "eligible_by_org": [{"org_type": key, "ad_count": values[0], "total_amount": amount_text(values[1])} for key, values in sorted(eligible_by_org.items())],
        "groups": list(group_totals.values()),
        "statistics": list(brand_totals.values()),
        "breakdown": [{"group": key[0], "brand": key[1], "org_type": key[2], "media_type": key[3], "ad_count": values[0], "total_amount": amount_text(values[1])} for key, values in sorted(breakdown.items())],
        "registered_names": [{"group": key[0], "brand": key[1], "raw_media_name": key[2], "media_type": key[3], "ad_count": values[0], "total_amount": amount_text(values[1])} for key, values in sorted(aliases.items())],
        "review_candidates": [{"raw_media_name": key[0], "media_type": key[1], "reason": key[2], "ad_count": values[0], "total_amount": amount_text(values[1])} for key, values in sorted(review.items())],
        "audit": dict(audit),
    }
    return fact_sheet, details, invalid_dates


def csv_safe(value):
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "@")) else text


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_safe(row.get(key, "")) for key in fieldnames})


def write_outputs(output_dir, fact_sheet, details, invalid_dates):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "fact_sheet.json").write_text(json.dumps(fact_sheet, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "report_data.json").write_text(json.dumps({"fact_sheet": fact_sheet, "records": details}, ensure_ascii=False), encoding="utf-8")
    write_csv(output_dir / "all_ads.csv", DETAIL_FIELDS, details)
    write_csv(output_dir / "media_summary.csv", ["group", "brand", "ad_count", "total_amount", "share_of_eligible_amount_pct", "previous_year_start_count"], fact_sheet["statistics"])
    write_csv(output_dir / "registered_names.csv", ["group", "brand", "raw_media_name", "media_type", "ad_count", "total_amount"], fact_sheet["registered_names"])
    write_csv(output_dir / "review_candidates.csv", ["raw_media_name", "media_type", "reason", "ad_count", "total_amount"], fact_sheet["review_candidates"])
    write_csv(output_dir / "invalid_start_dates.csv", ["원자료참조"] + RAW_FIELDS, invalid_dates)
    template = (BASE_DIR / "single_report_template.html").read_text(encoding="utf-8")
    payload = json.dumps({"fact_sheet": fact_sheet, "records": details}, ensure_ascii=False).replace("<", "\\u003c")
    report = template.replace("__REPORT_DATA__", payload).replace("__REPORT_TITLE__", html.escape(fact_sheet["topic"]))
    (output_dir / "report.html").write_text(report, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="정부광고 대표 매체군 자료 생성")
    parser.add_argument("--source", choices=["csv", "mysql"])
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--compare-csv", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--settings", type=Path, default=BASE_DIR / "settings.json")
    parser.add_argument("--open-report", action="store_true")
    parser.add_argument("--base-year", type=int, choices=range(2022, 2027))
    parser.add_argument("--compare-year", type=int, choices=range(2022, 2027))
    args = parser.parse_args(argv)
    settings = load_settings(args.settings)
    if args.base_year is not None:
        settings["year"] = str(args.base_year)
    if args.compare_year is not None:
        settings["compare_year"] = str(args.compare_year)
    if args.base_year is not None or args.compare_year is not None:
        if settings["year"] == settings.get("compare_year"):
            raise ValueError("기준연도와 비교연도는 달라야 합니다.")
        settings["period_policy"] = "year_pair"
    source_type = args.source or settings.get("source", "csv")
    groups, lookup = load_groups()
    if settings.get("compare_year"):
        if __package__:
            from .comparison import execute
        else:
            from comparison import execute
        execute(settings, args, groups, lookup, source_type)
        return
    if source_type == "csv":
        path = args.csv or PROJECT_DIR / "data" / f"{settings['year']}년도_정부광고집행내역_260930 기준.csv"
        if not path.is_file():
            raise SystemExit("원자료 CSV가 없습니다. media_analysis 폴더를 app.py 옆에 넣었는지 확인하세요.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source = {"mode": "CSV 원자료", "file_name": path.name, "sha256": digest, "provider": "한국언론진흥재단(프로젝트에 저장된 원자료)", "reference_date": "2026-09-30"}
        rows = csv_rows(path)
    else:
        source = {"mode": "기존 MySQL 읽기 전용 조회", "table": "ad_execution", "year_field": "집행연도", "provider": "기존 정부광고 DB", "reference_date": "DB에 적재된 자료 기준"}
        rows = mysql_rows(settings)
    print(f"{settings['year']}년 자료를 읽어 광고시작일 조건과 매체명을 확인합니다...")
    try:
        fact_sheet, details, invalid_dates = aggregate(rows, settings, groups, lookup, source)
    finally:
        close = getattr(rows, "close", None)
        if close:
            close()
    output_dir = args.output or BASE_DIR / settings.get("output_folder", "output")
    write_outputs(output_dir, fact_sheet, details, invalid_dates)
    print(f"분석 완료: 대표 매체 {len(fact_sheet['statistics'])}개, 광고내역 {len(details):,}행")
    for item in fact_sheet["groups"]:
        print(f"{item['group']}: {item['ad_count']:,}행 / {money(item['total_amount']):,.0f}원")
    print(f"전체 광고내역: {output_dir / 'all_ads.csv'}")
    print(f"화면에서 보기: {output_dir / 'report.html'}")
    print("기사 생성은 WRITE_ARTICLE.bat을 실행하세요.")
    if args.open_report:
        import webbrowser
        webbrowser.open((output_dir / "report.html").resolve().as_uri())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"분석 실패: {exc}")
