import json
import os
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymysql
from fastapi.testclient import TestClient

from app import app
from media_analysis import comparison, run_analysis as core
from media_analysis.write_article import build_article_analysis
from services.article_analysis import _period, pair_settings, prepare_pair
from services.article_repository import ArticleError
from article_test_support import Connection, make_repository, write_fixture_csvs


class ArticleWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        write_fixture_csvs(self.root)
        self.db = self.root/"articles.sqlite"
        self.repo = make_repository(self.db)
        self.patch_repo = patch("routers.articles.repository", self.repo)
        self.patch_root = patch.object(core, "PROJECT_DIR", self.root)
        self.patch_repo.start(); self.patch_root.start()
        self.addCleanup(self.patch_repo.stop); self.addCleanup(self.patch_root.stop)
        _period.cache_clear(); self.addCleanup(_period.cache_clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def prepare(self, base=2024, current=2026):
        response = self.client.post("/api/articles/prepare", json={"base_years":[base],"compare_years":[current]})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["article_ids"][0]

    def completed(self):
        article_id = self.prepare()
        token = self.repo.reserve_generation(article_id)
        self.repo.finish_generation(article_id,token,"시험 기사", "원자료를 대조했습니다.", {"model":"offline-test"})
        return self.repo.get(article_id)

    def review(self, article, passed=True, route="review"):
        return self.client.put(f"/api/articles/{article['id']}/{route}",json={"revision":article["revision"], "reviewer":"시험기자", "checks":{"numbers":passed,"scope":True,"claims":True,"sources":True},"comment":"근거 대조"})

    def test_all_twenty_ordered_pairs_obey_period_rules_and_reuse_nine_periods(self):
        result=self.client.post("/api/articles/prepare",json={"base_years":list(range(2022,2027)),"compare_years":list(range(2022,2027))})
        self.assertEqual(result.status_code,201,result.text)
        self.assertEqual(len(result.json()["article_ids"]),20)
        for pair in result.json()["pairs"]:
            article=self.repo.get(pair["id"]); fact=article["fact_sheet"]
            partial=2026 in (pair["base_year"],pair["current_year"])
            for year,period in fact["periods"].items():
                self.assertEqual(period["selected_total"]["ad_count"],1 if partial else 3)
                self.assertEqual(period["scope"]["start_on_or_before"],f"{year}-09-30" if partial else None)
            self.assertEqual(fact["scope"]["base_year"],str(pair["base_year"]))
        self.assertEqual(_period.cache_info().misses,9)

    def test_annual_note_has_no_fabricated_september_cutoff(self):
        fact=prepare_pair(2022,2025)["fact_sheet"]
        note=build_article_analysis(fact)["비교기준설명"]
        self.assertIn("연간 비교",note)
        self.assertNotIn("09-30",note)
        self.assertIsNone(fact["scope"]["base_cutoff"])

    def test_reverse_comparison_keeps_base_year_and_change_direction(self):
        settings=pair_settings(2026,2022)
        self.assertEqual(settings["year"],"2026")
        self.assertEqual(comparison.period_settings(settings,2022)["start_on_or_before"],"2022-09-30")
        row=comparison.compare_values({"ad_count":4,"total_amount":"100"},{"ad_count":2,"total_amount":"50"},100,100)
        self.assertEqual(row["amount_change_pct"],"-50.00")

    def test_self_comparison_bad_year_and_empty_selection_are_rejected(self):
        for body,expected in (({"base_years":[2022],"compare_years":[2022]},400),({"base_years":[2021],"compare_years":[2026]},422),({"base_years":[],"compare_years":[2026]},422)):
            self.assertEqual(self.client.post("/api/articles/prepare",json=body).status_code,expected)

    def test_missing_source_never_creates_zero_result(self):
        (self.root/"data/2023년도_정부광고집행내역_260930 기준.csv").unlink()
        response=self.client.post("/api/articles/prepare",json={"base_years":[2024],"compare_years":[2023]})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.repo.list(),[])

    def test_unreviewed_direct_approval_is_400(self):
        article=self.completed()
        response=self.client.put(f"/api/articles/{article['id']}/approve",json={"revision":article["revision"]})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.repo.get(article["id"])["status"],"검토대기")

    def test_failure_is_held_and_direct_approval_is_400(self):
        article=self.completed()
        self.assertEqual(self.review(article,False).json()["status"],"보류")
        self.assertEqual(self.client.put(f"/api/articles/{article['id']}/approve",json={"revision":article["revision"]}).status_code,400)
        self.assertEqual(self.repo.get(article["id"])["reviews"][0]["passed"],0)

    def test_all_pass_human_approval_persists_and_only_approved_are_public(self):
        article=self.completed(); other=self.completed()
        self.assertEqual(self.review(article).status_code,200)
        response=self.client.put(f"/api/articles/{article['id']}/approve",json={"revision":article["revision"]})
        self.assertEqual(response.json()["status"],"승인")
        self.assertEqual(response.json()["reviews"][0]["action"],"승인")
        restarted=type(self.repo)(lambda:Connection(self.db))
        self.assertEqual(restarted.get(article["id"])["reviewer"],"시험기자")
        public=self.client.get("/api/articles/published").json()["articles"]
        self.assertEqual([r["id"] for r in public],[article["id"]])
        self.assertNotIn(other["id"],[r["id"] for r in public])

    def test_edit_revokes_approval_requires_new_review_and_keeps_history(self):
        a=self.completed(); self.review(a); self.repo.approve(a["id"],a["revision"])
        response=self.client.put(f"/api/articles/{a['id']}",json={"revision":a["revision"],"title":a["title"],"body":"수정한 원고입니다."})
        b=response.json()
        self.assertEqual(b["status"],"검토대기"); self.assertIsNone(b["review_checks"])
        self.assertEqual(b["revision"],a["revision"]+1)
        self.assertEqual(len(b["reviews"]),2)
        self.assertEqual(self.client.get("/api/articles/published").json()["articles"],[])
        self.assertEqual(self.client.put(f"/api/articles/{a['id']}/approve",json={"revision":b["revision"]}).status_code,400)
        self.assertEqual(self.client.put(f"/api/articles/{a['id']}/approve",json={"revision":a["revision"]}).status_code,409)
        self.review(b); self.repo.approve(b["id"],b["revision"])

    def test_explicit_hold_even_all_pass_requires_review_again(self):
        a=self.completed(); self.assertEqual(self.review(a,route="hold").json()["status"],"보류")
        with self.assertRaises(ArticleError):self.repo.approve(a["id"],a["revision"])
        self.review(a); self.repo.approve(a["id"],a["revision"])

    def test_blank_content_and_unsafe_boolean_are_rejected(self):
        a=self.completed()
        result=self.client.put(f"/api/articles/{a['id']}",json={"revision":a["revision"],"title":" ","body":" "})
        self.assertEqual(result.status_code,422)
        payload={"revision":a["revision"],"reviewer":"시험기자","checks":{"numbers":"false","scope":True,"claims":True,"sources":True}}
        self.assertEqual(self.client.put(f"/api/articles/{a['id']}/review",json=payload).status_code,422)

    def test_cannot_smuggle_checks_into_approval(self):
        a=self.completed()
        self.assertEqual(self.client.put(f"/api/articles/{a['id']}/approve",json={"revision":a["revision"],"status":"승인","checks":dict.fromkeys(("numbers","scope","claims","sources"),True)}).status_code,422)

    def test_generation_claim_blocks_duplicate_and_completed_is_not_charged_again(self):
        article_id=self.prepare(); token=self.repo.reserve_generation(article_id)
        with self.assertRaises(ArticleError): self.repo.reserve_generation(article_id)
        self.repo.finish_generation(article_id,token,"제목","본문",{})
        with patch("routers.articles.generate_fact") as generate:
            self.assertEqual(self.client.post(f"/api/articles/{article_id}/generate").status_code,200)
        generate.assert_not_called()

    def test_concurrent_generation_claims_only_one_request(self):
        article_id=self.prepare()
        def claim():
            try:return bool(self.repo.reserve_generation(article_id))
            except ArticleError as exc:
                self.assertEqual(exc.status_code,409)
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:claim(),range(2)))
        self.assertEqual(results.count(True),1)

    def test_installed_openai_sdk_with_mock_http_transport(self):
        import httpx
        from openai import OpenAI
        from media_analysis.write_article import generate_fact
        prepared=prepare_pair(2022,2025)
        seen=[]
        def transport(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={"id":"resp_offline", "object":"response", "created_at":0,"status":"completed","model":"sdk-offline-model","output":[{"type":"message","id":"msg_offline","role":"assistant","status":"completed","content":[{"type":"output_text","text":"시험 제목\n\n경어체 기사 본문입니다.","annotations":[]}]}],"usage":None})
        def factory(**kwargs):
            return OpenAI(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(transport)))
        text,record=generate_fact(prepared["fact_sheet"],prepared["settings"],"offline-sdk-test",factory)
        self.assertIn("경어체",text)
        self.assertEqual(record["model"],"sdk-offline-model")
        self.assertEqual(len(seen),1)
        payload=json.loads(seen[0]["input"])
        self.assertIn("연간 비교",payload["기사용분석"]["비교기준설명"])
        self.assertIsNone(payload["scope"]["base_cutoff"])

    def test_real_generation_route_uses_mock_sdk_once_and_stores_snapshot(self):
        article_id=self.prepare()
        factory=MagicMock()
        factory.return_value.__enter__.return_value.responses.create.return_value=types.SimpleNamespace(output_text="시험 제목\n\n기사 본문입니다.",status="completed",model="mock-model",id="mock-response",usage=None)
        with patch.dict(os.environ,{"OPENAI_API_KEY":"offline-test"}),patch.dict("sys.modules",{"openai":types.SimpleNamespace(OpenAI=factory)}):
            first=self.client.post(f"/api/articles/{article_id}/generate")
            second=self.client.post(f"/api/articles/{article_id}/generate")
        self.assertEqual(first.status_code,200,first.text);self.assertEqual(second.status_code,200)
        self.assertEqual(factory.call_count,1)
        self.assertEqual(first.json()["generation_record"]["model"],"mock-model")
        self.assertNotIn("offline-test",json.dumps(first.json()))

    def test_generation_failure_is_recorded_and_retry_can_succeed(self):
        article_id=self.prepare()
        with patch.dict(os.environ,{"OPENAI_API_KEY":"offline-test"}),patch.dict("sys.modules",{"openai":types.SimpleNamespace(OpenAI=MagicMock())}),patch("routers.articles.generate_fact",side_effect=RuntimeError("secret-input-must-not-appear")):
            response=self.client.post(f"/api/articles/{article_id}/generate")
        self.assertEqual(response.status_code,502)
        self.assertNotIn("secret-input",response.text)
        self.assertEqual(self.repo.get(article_id)["generation_status"],"실패")
        token=self.repo.reserve_generation(article_id)
        self.repo.finish_generation(article_id,token,"제목","본문",{})

    def test_no_key_never_reserves_a_paid_request(self):
        article_id=self.prepare()
        with patch.dict(os.environ,{"OPENAI_API_KEY":""}):
            self.assertEqual(self.client.post(f"/api/articles/{article_id}/generate").status_code,503)
        self.assertEqual(self.repo.get(article_id)["generation_status"],"대기")

    def test_schema_error_is_actionable_and_skips_aggregation(self):
        with patch.object(self.repo,"ready",side_effect=pymysql.err.ProgrammingError(1146,"missing")),patch("routers.articles.prepare_pair") as aggregate:
            self.assertFalse(self.client.get("/api/articles/config").json()["db_ready"])
            self.assertEqual(self.client.post("/api/articles/prepare",json={"base_years":[2024],"compare_years":[2026]}).status_code,503)
        aggregate.assert_not_called()

    def test_editor_and_public_pages_and_static_files_are_served(self):
        for path in ("/articles","/articles/published","/static/js/articles.js","/static/css/articles.css","/static/js/published_articles.js"):
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.get("/api/articles/999999").status_code,404)


if __name__=="__main__":unittest.main()
