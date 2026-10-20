import json
import tempfile
import types
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_analysis import run_analysis as analysis
from media_analysis import write_article
from media_analysis import comparison


class MediaAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.settings = analysis.load_settings()
        self.groups, self.lookup = analysis.load_groups()

    def row(self, media="조선일보", start="20240930", org="국가행정기관", amount="100.10", media_type="인쇄"):
        return {"기관분류": org, "기관명": "시험기관", "매체구분": media_type, "매체명": media, "광고명": "시험광고", "광고료": amount, "수수료": "0", "총계(VAT포함)": amount, "광고시작일": start, "광고종료일": "20241231"}

    def analyze(self, rows):
        return analysis.aggregate(((row, f"fixture:{i}") for i, row in enumerate(rows)), self.settings, self.groups, self.lookup, {"mode": "시험 자료"})

    def test_cutoff_org_and_missing_dates(self):
        facts, details, bad_dates = self.analyze([
            self.row(start="20240930"), self.row(start="20241001"),
            self.row(start="20231201"), self.row(org="지방행정기관"),
            self.row(org="지방공기업"), self.row(start=""),
        ])
        self.assertEqual(len(details), 2)
        self.assertEqual(facts["selected_total"]["total_amount"], "200.20")
        self.assertEqual(facts["audit"]["selected_previous_year_start_rows"], 1)
        self.assertEqual(len(bad_dates), 1)

    def test_optional_lower_bound(self):
        self.settings["start_on_or_after"] = "2024-01-01"
        facts, details, _ = self.analyze([self.row(start="20231231"), self.row(start="20240101")])
        self.assertEqual(len(details), 1)
        self.assertEqual(facts["scope"]["start_on_or_after"], "2024-01-01")

    def test_exact_aliases_and_no_fuzzy_match(self):
        facts, details, _ = self.analyze([
            self.row(media="동아닷컴", media_type="인터넷"),
            self.row(media="동아방송", media_type="인터넷"),
            self.row(media="오마이뉴스(OhmyNews)", media_type="인터넷"),
            self.row(media="시민언론 민들레", media_type="인터넷"),
            self.row(media="TV조선", media_type="해외"),
        ])
        self.assertEqual({row["통합매체명"] for row in details}, {"동아일보", "오마이뉴스", "시민언론 민들레"})
        self.assertEqual(facts["eligible_total"]["ad_count"], 5)
        self.assertEqual(facts["unclassified_total"]["ad_count"], 2)
        self.assertEqual(len(facts["review_candidates"]), 2)

    def test_decimal_refunds_duplicates_and_denominator(self):
        rows = [self.row(amount="0.1"), self.row(amount="0.2"), self.row(amount="-0.1"), self.row(media="다른매체", amount="0.8")]
        facts, _, _ = self.analyze(rows)
        self.assertEqual(Decimal(facts["selected_total"]["total_amount"]), Decimal("0.2"))
        self.assertEqual(Decimal(facts["eligible_total"]["total_amount"]), Decimal("1.0"))
        self.assertEqual(facts["groups"][0]["share_of_eligible_amount_pct"], "20.0000")
        duplicate_facts, duplicate_rows, _ = self.analyze([rows[0], rows[0]])
        self.assertEqual(len(duplicate_rows), 2)
        self.assertEqual(duplicate_facts["audit"]["selected_exact_duplicate_extra_rows"], 1)

    def test_unreadable_money_stops_instead_of_silent_zero(self):
        for value in ("확인불가", "", None, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.analyze([self.row(amount=value)])

    def test_output_contains_all_rows_and_escaped_payload(self):
        row = self.row()
        row["광고명"] = "</script><script>bad()</script>"
        facts, details, bad_dates = self.analyze([row])
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            analysis.write_outputs(folder, facts, details, bad_dates)
            exported = json.loads((folder / "report_data.json").read_text(encoding="utf-8"))
            self.assertEqual(exported["records"][0]["광고명"], row["광고명"])
            self.assertNotIn(row["광고명"], (folder / "report.html").read_text(encoding="utf-8"))
            self.assertEqual(len(list(analysis.csv_rows(folder / "all_ads.csv"))), 1)

    def test_mysql_is_parameterized_select_and_closes(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchmany.side_effect = [[self.row()], []]
        database = types.SimpleNamespace(get_db=MagicMock(return_value=connection))
        with patch.dict("sys.modules", {"database": database}):
            rows = list(analysis.mysql_rows(self.settings))
        sql, params = cursor.execute.call_args.args
        self.assertTrue(sql.startswith("SELECT "))
        self.assertNotIn("LIMIT", sql)
        self.assertEqual(params, ("2024", "국가행정기관", "공공기관"))
        self.assertEqual(len(rows), 1)
        connection.close.assert_called_once()

    def test_article_uses_one_api_request_and_records_actual_model(self):
        base, _, _ = self.analyze([self.row()])
        settings = comparison.period_settings(self.settings, "2026")
        current, _, _ = analysis.aggregate([(self.row(start="20260930", amount="150.15"), "fixture:1")], settings, self.groups, self.lookup, {"mode": "시험 자료"})
        facts = comparison.build_comparison(base, current, self.settings)
        client_factory = MagicMock()
        response = types.SimpleNamespace(output_text="시험 응답", status="completed", model="actual-model-id", id="test-response-id", usage=None)
        call = client_factory.return_value.__enter__.return_value.responses.create
        call.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fact_sheet.json"
            path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
            article, record = write_article.generate(path, self.settings, "offline-value", client_factory)
            self.assertEqual(article, "시험 응답")
            self.assertEqual(record["model"], "actual-model-id")
            payload = json.loads(call.call_args.kwargs["input"])
            self.assertEqual({k: v for k, v in payload.items() if k != "기사용분석"}, facts)
            self.assertEqual(payload["기사용분석"]["유형별매체군비교"][0]["amount_change_pct"], "50.00")
            self.assertEqual(record["fact_sheet"], payload)
            self.assertEqual(call.call_args.kwargs["instructions"], write_article.PROMPT)
            self.assertEqual(facts["statistics"][0]["amount_change_pct"], "50.00")
            self.assertEqual(set(facts["periods"]), {"2024", "2026"})
            self.assertEqual(call.call_count, 1)
            self.assertNotIn("offline-value", json.dumps(record))
            self.settings["compare_year"] = "2025"
            with self.assertRaises(ValueError):
                write_article.generate(path, self.settings, "offline-value", client_factory)
            self.assertEqual(call.call_count, 1)

    def test_article_rejects_old_single_year_before_api_call(self):
        facts, _, _ = self.analyze([self.row()])
        client_factory = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fact_sheet.json"
            path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "두 연도 비교"):
                write_article.generate(path, self.settings, "offline-value", client_factory)
        client_factory.assert_not_called()

    def test_article_separates_print_broadcast_online_and_combines_orgs(self):
        base_rows = [self.row(amount="100"), self.row(org="공공기관", amount="200"), self.row(media_type="인터넷", amount="1000"), self.row(media="TV조선", media_type="방송", amount="100")]
        current_rows = [self.row(start="20260930", amount="60"), self.row(start="20260930", org="공공기관", amount="120"), self.row(start="20260930", media_type="인터넷", amount="2000"), self.row(start="20260930", media="TV조선", media_type="방송", amount="90")]
        base, _, _ = self.analyze(base_rows)
        period = comparison.period_settings(self.settings, "2026")
        current, _, _ = analysis.aggregate(((r, str(i)) for i, r in enumerate(current_rows)), period, self.groups, self.lookup, {"mode": "시험 자료"})
        facts = comparison.build_comparison(base, current, self.settings)
        report = write_article.build_article_analysis(facts)
        rows = {(r["brand"], r["media_type"]): r for r in report["유형별개별매체비교"]}
        printed = rows[("조선일보", "인쇄")]
        online = rows[("조선일보", "인터넷")]
        self.assertEqual(printed["base_amount"], "300")
        self.assertEqual(printed["current_amount"], "180")
        self.assertEqual(printed["amount_change_pct"], "-40.00")
        self.assertEqual(printed["기사언급가능지표"], ["금액"])
        self.assertEqual(online["amount_change_pct"], "100.00")
        self.assertEqual(rows[("TV조선", "방송")]["amount_change_pct"], "-10.00")
        self.assertEqual(len(report["기사후보"]["인쇄"]["매체군"]), 1)
        self.assertIn("이전 연도 시작 광고도 포함", report["비교기준설명"])
        self.assertEqual(len(report["예산편성배경"]["출처"]), 2)
        # 타입별 합계가 깨진 자료는 API를 호출하기 전에 중단한다.
        facts["periods"]["2024"]["breakdown"].pop()
        client = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fact_sheet.json"
            path.write_text(json.dumps(facts, ensure_ascii=False))
            with self.assertRaisesRegex(ValueError, "유형별 집계"):
                write_article.generate(path, self.settings, "offline-value", client)
        client.assert_not_called()

    def test_article_threshold_and_rounded_amounts(self):
        self.assertEqual(write_article.eligible_metrics({"count_change_pct": "9.99", "amount_change_pct": "-9.99"}), [])
        self.assertEqual(write_article.eligible_metrics({"count_change_pct": "10.00", "amount_change_pct": "-10.00"}), ["건수", "금액"])
        self.assertEqual(write_article.eligible_metrics({"count_change_pct": None, "amount_change_pct": None}), [])
        self.assertEqual(write_article.article_amount("1700000000"), "약 17억 원")
        self.assertEqual(write_article.article_amount("284230102"), "약 3억 원")
        self.assertEqual(write_article.article_amount("41520000"), "약 4152만 원")
        self.assertEqual(write_article.article_rate("-43.41"), "43.4%")

    def test_comparison_changes_shares_and_zero_baseline(self):
        result = comparison.compare_values({"ad_count": 10, "total_amount": "100"}, {"ad_count": 8, "total_amount": "80"}, Decimal("1000"), Decimal("400"))
        self.assertEqual(result["amount_change"], "-20")
        self.assertEqual(result["amount_change_pct"], "-20.00")
        self.assertEqual(result["count_change"], -2)
        self.assertEqual(result["count_change_pct"], "-20.00")
        self.assertEqual(result["share_change_pp"], "10.0000")
        zero = comparison.compare_values({}, {"ad_count": 2, "total_amount": "25"}, Decimal("100"), Decimal("100"))
        self.assertIsNone(zero["amount_change_pct"])
        self.assertIsNone(zero["count_change_pct"])
        self.assertEqual(zero["amount_change"], "25")
        self.assertEqual(zero["count_change"], 2)

    def test_one_execution_reads_both_years_and_writes_complete_comparison(self):
        import csv
        rows = [[self.row(start="20240930", amount="100"), self.row(start="20241001", amount="999")],
                [self.row(start="20260930", amount="60"), self.row(media="시민언론민들레", start="20260930", amount="5"), self.row(start="20261001", amount="999")]]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            paths = [folder / "base.csv", folder / "current.csv"]
            for path, records in zip(paths, rows):
                with path.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=analysis.RAW_FIELDS)
                    writer.writeheader()
                    writer.writerows(records)
            args = types.SimpleNamespace(csv=paths[0], compare_csv=paths[1], output=folder / "result", open_report=False)
            comparison.execute(self.settings, args, self.groups, self.lookup, "csv")
            fact = json.loads((args.output / "fact_sheet.json").read_text())
            self.assertEqual(fact["scope"]["base_cutoff"], "2024-09-30")
            self.assertEqual(fact["scope"]["current_cutoff"], "2026-09-30")
            self.assertEqual(fact["selected_comparison"]["amount_change"], "-35")
            self.assertEqual(fact["statistics"][0]["amount_change_pct"], "-40.00")
            self.assertEqual(fact["statistics"][-1]["current_count"], 1)
            exported = json.loads((args.output / "report_data.json").read_text())
            self.assertEqual(len(exported["records"]), 3)
            self.assertEqual({r["자료연도"] for r in exported["records"]}, {"2024", "2026"})
            self.assertEqual(len(list(analysis.csv_rows(args.output / "all_ads_2024.csv"))), 1)
            self.assertEqual(len(list(analysis.csv_rows(args.output / "all_ads_2026.csv"))), 2)

    def test_comparison_moves_lower_bound_to_each_year(self):
        self.settings["period_policy"] = "custom"
        self.settings["start_on_or_after"] = "2024-01-01"
        period = comparison.period_settings(self.settings, "2026")
        self.assertEqual(period["start_on_or_after"], "2026-01-01")
        self.assertEqual(period["start_on_or_before"], "2026-09-30")


if __name__ == "__main__":
    unittest.main()
