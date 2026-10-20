"""MySQL 트랜잭션으로 기사 버전·검수·승인을 함께 관리한다."""

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from database import get_db

CHECK_KEYS = ("numbers", "scope", "claims", "sources")


class ArticleError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def dump(value):
    return json.dumps(value, ensure_ascii=False)


class ArticleRepository:
    def __init__(self, connection_factory=get_db):
        self.connection_factory = connection_factory

    @contextmanager
    def transaction(self):
        conn = self.connection_factory()
        try:
            with conn.cursor() as cursor:
                yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ready(self):
        with self.transaction() as cur:
            cur.execute("SELECT id FROM news_articles LIMIT 0")
            cur.execute("SELECT id FROM news_reviews LIMIT 0")

    def _row(self, cur, article_id, revision=None):
        cur.execute("SELECT * FROM news_articles WHERE id=%s FOR UPDATE", (article_id,))
        row = cur.fetchone()
        if not row:
            raise ArticleError(404, "기사를 찾을 수 없습니다.")
        if revision is not None and row["revision"] != revision:
            raise ArticleError(409, "다른 창에서 기사가 변경됐습니다. 다시 불러온 뒤 검수하세요.")
        return row

    @staticmethod
    def serialize(row, detail=False):
        result = dict(row)
        result.pop("generation_token", None)
        for key in ("created_at", "updated_at", "reviewed_at"):
            value = result.get(key)
            if value:
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[key] = str(value).replace(" ", "T") + "Z"
        if detail:
            for key in ("fact_sheet", "settings_json", "generation_record", "review_checks"):
                result[key] = json.loads(result[key]) if result.get(key) else None
        return result

    def list(self, approved_only=False):
        fields = "id,base_year,current_year,title,status,generation_status,revision,updated_at"
        if approved_only:
            fields += ",body"
        with self.transaction() as cur:
            cur.execute(f"SELECT {fields} FROM news_articles " + ("WHERE status='승인' " if approved_only else "") + "ORDER BY id DESC LIMIT 200")
            rows = [self.serialize(row) for row in cur.fetchall()]
            return sorted(rows, key=lambda row: (row["base_year"], row["current_year"], -row["id"]))

    def get(self, article_id):
        with self.transaction() as cur:
            row = self._row(cur, article_id)
            result = self.serialize(row, True)
            cur.execute("SELECT article_revision,reviewer,checks_json,passed,action,comment,reviewed_at FROM news_reviews WHERE article_id=%s ORDER BY id DESC", (article_id,))
            result["reviews"] = [dict(r, checks_json=json.loads(r["checks_json"]), reviewed_at=str(r["reviewed_at"])) for r in cur.fetchall()]
            return result

    def create_many(self, prepared):
        ids = []
        with self.transaction() as cur:
            for item in prepared:
                stamp = now()
                settings = item["settings"]
                cur.execute("INSERT INTO news_articles (base_year,current_year,title,body,fact_sheet,settings_json,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (int(settings["year"]), int(settings["compare_year"]), "", "", dump(item["fact_sheet"]), dump(settings), stamp, stamp))
                ids.append(cur.lastrowid)
        return ids

    def reserve_generation(self, article_id):
        with self.transaction() as cur:
            row = self._row(cur, article_id)
            if row["generation_status"] == "완료":
                return None  # 같은 요청이 다시 와도 유료 API를 중복 호출하지 않는다.
            if row["generation_status"] == "생성중":
                raise ArticleError(409, "이미 생성 중입니다. 중복 요청하지 않고 결과를 기다립니다.")
            token = str(uuid.uuid4())
            cur.execute("UPDATE news_articles SET generation_status='생성중',generation_token=%s,generation_error=NULL,updated_at=%s WHERE id=%s", (token, now(), article_id))
            return token

    def finish_generation(self, article_id, token, title, body, record):
        with self.transaction() as cur:
            row = self._row(cur, article_id)
            if row["generation_token"] != token or row["generation_status"] != "생성중":
                raise ArticleError(409, "기사 생성 요청의 상태가 바뀌었습니다.")
            cur.execute("UPDATE news_articles SET title=%s,body=%s,generation_record=%s,generation_status='완료',generation_token=NULL,status='검토대기',revision=revision+1,review_revision=NULL,review_checks=NULL,reviewer=NULL,reviewed_at=NULL,updated_at=%s WHERE id=%s", (title, body, dump(record), now(), article_id))

    def fail_generation(self, article_id, token, message):
        with self.transaction() as cur:
            cur.execute("UPDATE news_articles SET generation_status='실패',generation_error=%s,generation_token=NULL,updated_at=%s WHERE id=%s AND generation_token=%s", (message[:300], now(), article_id, token))

    def save_content(self, article_id, revision, title, body):
        if not title.strip() or not body.strip():
            raise ArticleError(400, "제목과 본문을 입력하세요.")
        with self.transaction() as cur:
            row = self._row(cur, article_id, revision)
            if row["generation_status"] != "완료":
                raise ArticleError(400, "기사 생성이 완료된 뒤 수정할 수 있습니다.")
            if row["title"] != title or row["body"] != body:
                cur.execute("UPDATE news_articles SET title=%s,body=%s,revision=revision+1,status='검토대기',review_revision=NULL,review_checks=NULL,reviewer=NULL,reviewed_at=NULL,updated_at=%s WHERE id=%s", (title, body, now(), article_id))

    @staticmethod
    def passed(checks):
        return set(checks) == set(CHECK_KEYS) and all(checks[key] is True for key in CHECK_KEYS)

    def _record_review(self, cur, row, reviewer, checks, comment, action):
        cur.execute("INSERT INTO news_reviews (article_id,article_revision,reviewer,checks_json,passed,action,comment,reviewed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (row["id"], row["revision"], reviewer, dump(checks), self.passed(checks), action, comment, now()))

    def review(self, article_id, revision, reviewer, checks, comment, hold=False):
        if not reviewer.strip():
            raise ArticleError(400, "검토자 이름을 입력하세요.")
        with self.transaction() as cur:
            row = self._row(cur, article_id, revision)
            if row["generation_status"] != "완료" or not row["body"].strip():
                raise ArticleError(400, "생성이 완료된 기사만 검수할 수 있습니다.")
            status = "검토대기" if self.passed(checks) and not hold else "보류"
            cur.execute("UPDATE news_articles SET review_checks=%s,review_revision=%s,reviewer=%s,reviewed_at=%s,status=%s,updated_at=%s WHERE id=%s", (dump(checks), row["revision"], reviewer, now(), status, now(), article_id))
            self._record_review(cur, row, reviewer, checks, comment, "보류" if hold else "검수")

    def approve(self, article_id, revision):
        with self.transaction() as cur:
            row = self._row(cur, article_id, revision)
            checks = json.loads(row["review_checks"]) if row["review_checks"] else {}
            if row["generation_status"] != "완료" or row["review_revision"] != row["revision"] or not self.passed(checks) or not row["reviewer"] or row["status"] == "보류" or not row["title"].strip() or not row["body"].strip():
                raise ArticleError(400, "검수 미통과 기사는 승인할 수 없습니다. 현재 원고의 4항목을 모두 통과한 뒤 검수 결과를 저장하세요.")
            if row["status"] != "승인":
                cur.execute("UPDATE news_articles SET status='승인',updated_at=%s WHERE id=%s", (now(), article_id))
                self._record_review(cur, row, row["reviewer"], checks, "검수 통과 후 사람이 승인했습니다.", "승인")
