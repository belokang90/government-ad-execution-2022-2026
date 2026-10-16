"""실제 DB 없이 화면 제공과 기존 조회 API 계약을 검증한다."""

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.conn = MagicMock()
        self.cur = self.conn.cursor.return_value.__enter__.return_value
        self.db_patch = patch("routers.ads.get_db", return_value=self.conn)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.client.close)

    def test_home_and_static_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("정부광고 집행내역", response.text)
        self.assertIn('/static/css/dashboard.css', response.text)
        self.assertIn('/static/js/dashboard.js', response.text)
        css = self.client.get("/static/css/dashboard.css")
        js = self.client.get("/static/js/dashboard.js")
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertIn("text/css", css.headers["content-type"])
        self.assertIn("javascript", js.headers["content-type"])
        self.assertIn("function fetchData", js.text)
        self.conn.cursor.assert_not_called()

    def test_init_returns_filter_lists_and_total(self):
        self.cur.fetchall.side_effect = [
            [{"매체구분": "인터넷", "ad_count": 2, "total_spend": Decimal("110.50")}],
            [{"기관분류": "지자체"}], [{"매체구분": "인터넷"}], [{"yr": "2026"}],
        ]
        self.cur.fetchone.return_value = {"cnt": 2}
        response = self.client.get("/api/init-data")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["total_count"], 2)
        self.assertEqual(result["years"], ["2026"])
        self.assertEqual(result["org_types"], ["지자체"])
        self.assertEqual(result["media_types"], ["인터넷"])
        self.assertEqual(result["summary"][0]["total_spend"], 110.5)
        self.conn.close.assert_called_once()

    def test_summary_uses_year_for_aggregate(self):
        self.cur.fetchall.return_value = []
        self.cur.fetchone.return_value = {"cnt": 0}
        response = self.client.get("/api/summary", params={"year": "2025"})
        self.assertEqual(response.json(), {"success": True, "summary": [], "filtered_count": 0})
        for call in self.cur.execute.call_args_list:
            self.assertIn("집행연도 = %s", call.args[0])
            self.assertEqual(call.args[1], ["2025"])
        self.conn.close.assert_called_once()

    def test_search_keeps_full_totals_separate_from_page(self):
        self.cur.fetchall.return_value = [{"기관명": "시험기관", "광고시작일": date(2025, 1, 2)}]
        self.cur.fetchone.return_value = {"cnt": 3000, "total_sum": Decimal("900.25")}
        response = self.client.get("/api/search-ads", params={
            "keyword": "테스트", "org_type": "지자체", "media_type": "인터넷",
            "year": "2025", "month": "01", "sort_col": "총계(VAT포함)",
            "sort_dir": "DESC", "limit": 1, "offset": 2,
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["광고시작일"], "2025-01-02")
        self.assertEqual(result["total_filtered"], 3000)
        self.assertEqual(result["total_sum"], 900.25)
        page_call, total_call = self.cur.execute.call_args_list
        filters = ["%테스트%"] * 3 + ["지자체", "인터넷", "2025", "%01"]
        self.assertEqual(page_call.args[1], filters + [1, 2])
        self.assertEqual(total_call.args[1], filters)
        self.assertIn("ORDER BY `총계(VAT포함)` DESC", page_call.args[0])
        self.assertNotIn("LIMIT", total_call.args[0])
        self.conn.close.assert_called_once()

    def test_invalid_sort_column_is_not_sql(self):
        self.cur.fetchall.return_value = []
        self.cur.fetchone.return_value = {"cnt": 0, "total_sum": None}
        dangerous = "기관명; DROP TABLE ad_execution"
        response = self.client.get("/api/search-ads", params={"sort_col": dangerous})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_sum"], 0)
        query = self.cur.execute.call_args_list[0].args[0]
        self.assertNotIn(dangerous, query)
        self.assertNotIn("ORDER BY", query)

    def test_init_reuses_grouped_count_and_sum(self):
        self.cur.fetchall.side_effect = [
            [
                {"매체구분": "인터넷", "ad_count": 2500, "total_spend": Decimal("900.25")},
                {"매체구분": None, "ad_count": 2, "total_spend": None},
                {"매체구분": "인쇄", "ad_count": 500, "total_spend": Decimal("110.75")},
            ],
            [{"기관분류": "지자체"}], [{"매체구분": "인터넷"}], [{"yr": "2026"}],
        ]
        result = self.client.get("/api/init-data").json()
        self.assertEqual(result["total_count"], 3002)
        self.assertEqual(result["total_sum"], 1011)
        self.assertEqual(self.cur.execute.call_count, 4)
        self.cur.fetchone.assert_not_called()

    def test_summary_only_init_runs_one_query(self):
        groups = [
            {"매체구분": "인터넷", "ad_count": 3, "total_spend": Decimal("110.25")},
            {"매체구분": None, "ad_count": 2, "total_spend": None},
        ]
        self.cur.fetchall.return_value = groups
        result = self.client.get("/api/init-data", params={"include_filters": "false"}).json()
        self.assertEqual(result["total_count"], 5)
        self.assertEqual(result["total_sum"], 110.25)
        self.assertEqual(len(result["summary"]), 2)
        self.assertEqual(result["org_types"], [])
        self.assertEqual(result["media_types"], [])
        self.assertEqual(result["years"], [])
        self.assertEqual(self.cur.execute.call_count, 1)
        self.assertIn("GROUP BY 매체구분", self.cur.execute.call_args.args[0])
        self.conn.close.assert_called_once()

    def test_summary_diagnostic_logs_connection_and_aggregation_separately(self):
        self.cur.fetchall.return_value = [
            {"매체구분": "인터넷", "ad_count": 2, "total_spend": Decimal("110.25")}
        ]
        with patch("routers.ads.perf_counter", side_effect=[0, 0, 0.125, 0.125, 9.125, 9.5]), \
                patch("routers.ads.logger.info") as log:
            response = self.client.get("/api/init-data", params={"include_filters": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_count"], 2)
        self.assertEqual(response.json()["total_sum"], 110.25)
        self.assertEqual(self.cur.execute.call_count, 1)
        log.assert_any_call("[로딩 진단] 상단 요약 DB 연결: %.3f초", 0.125)
        log.assert_any_call("[로딩 진단] 상단 요약 전체 집계: %.3f초", 9.0)
        log.assert_any_call("[로딩 진단] %s 서버 처리: %.3f초", "상단 요약", 9.5)

    def test_filter_options_keep_original_values_and_order(self):
        self.cur.fetchall.side_effect = [
            [{"기관분류": "공기업"}, {"기관분류": "지자체"}],
            [{"매체구분": "방송"}, {"매체구분": "인터넷"}],
            [{"yr": "2026"}, {"yr": "2025"}],
        ]
        result = self.client.get("/api/filter-options").json()
        self.assertEqual(result, {
            "success": True, "org_types": ["공기업", "지자체"],
            "media_types": ["방송", "인터넷"], "years": ["2026", "2025"],
        })
        self.assertEqual(self.cur.execute.call_count, 3)
        for call in self.cur.execute.call_args_list:
            self.assertIn("SELECT DISTINCT", call.args[0])
            self.assertIn("ORDER BY", call.args[0])
            self.assertNotIn("SUM(", call.args[0])
        self.conn.close.assert_called_once()

    def test_year_summary_counts_all_media_groups_once(self):
        self.cur.fetchall.return_value = [
            {"매체구분": "인터넷", "ad_count": 3, "total_spend": Decimal("110")},
            {"매체구분": None, "ad_count": 2, "total_spend": None},
        ]
        result = self.client.get("/api/summary", params={"year": "2026"}).json()
        self.assertEqual(result["filtered_count"], 5)
        self.assertEqual(self.cur.execute.call_count, 1)
        self.cur.fetchone.assert_not_called()

    def test_page_only_skips_full_count_and_sum(self):
        self.cur.fetchall.return_value = [{"기관명": "시험기관"}]
        result = self.client.get("/api/search-ads", params={
            "keyword": "테스트", "include_totals": "false", "offset": 2500,
        }).json()
        self.assertEqual(result["data"], [{"기관명": "시험기관"}])
        self.assertIsNone(result["total_filtered"])
        self.assertIsNone(result["total_sum"])
        self.assertEqual(self.cur.execute.call_count, 1)
        self.cur.fetchone.assert_not_called()
        self.assertEqual(self.cur.execute.call_args.args[1], ["%테스트%"] * 3 + [2500, 2500])

    def test_gzip_preserves_large_response(self):
        self.cur.fetchall.return_value = [
            {"기관명": "테스트기관", "광고명": "정부광고 집행내역", "광고료": 110} for _ in range(2500)
        ]
        self.cur.fetchone.return_value = {"cnt": 2500, "total_sum": Decimal("275000")}
        plain = self.client.get("/api/search-ads", headers={"Accept-Encoding": "identity"})
        compressed = self.client.get("/api/search-ads", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(compressed.headers["content-encoding"], "gzip")
        self.assertEqual(plain.json(), compressed.json())
        self.assertLess(int(compressed.headers["content-length"]), int(plain.headers["content-length"]))

    def test_query_failure_closes_connection(self):
        self.cur.execute.side_effect = RuntimeError("test query error")
        response = self.client.get("/api/summary")
        self.assertEqual(response.status_code, 500)
        self.conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
