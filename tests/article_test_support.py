"""네트워크 없이 저장·트랜잭션을 검증하기 위한 SQLite 어댑터. 운영은 MySQL."""
import csv
import sqlite3
from pathlib import Path

from media_analysis.run_analysis import RAW_FIELDS
from services.article_repository import ArticleRepository


SCHEMA = """
CREATE TABLE news_articles (
id INTEGER PRIMARY KEY AUTOINCREMENT,base_year INTEGER,current_year INTEGER,title TEXT DEFAULT '',body TEXT NOT NULL,
fact_sheet TEXT NOT NULL,settings_json TEXT NOT NULL,generation_record TEXT,generation_status TEXT DEFAULT '대기',
generation_token TEXT,generation_error TEXT,status TEXT DEFAULT '검토대기',revision INTEGER DEFAULT 1,
review_revision INTEGER,review_checks TEXT,reviewer TEXT,reviewed_at TEXT,created_at TEXT,updated_at TEXT);
CREATE TABLE news_reviews (
id INTEGER PRIMARY KEY AUTOINCREMENT,article_id INTEGER NOT NULL REFERENCES news_articles(id),article_revision INTEGER,
reviewer TEXT,checks_json TEXT,passed INTEGER,action TEXT,comment TEXT,reviewed_at TEXT);
"""


class Cursor:
    def __init__(self, cursor): self.cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): self.cursor.close()
    def execute(self, sql, params=()): return self.cursor.execute(sql.replace("%s", "?").replace(" FOR UPDATE", ""), params)
    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row is not None else None
    def fetchall(self): return [dict(row) for row in self.cursor.fetchall()]
    @property
    def lastrowid(self): return self.cursor.lastrowid


class Connection:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("BEGIN IMMEDIATE")
    def cursor(self): return Cursor(self.conn.cursor())
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()


def make_repository(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return ArticleRepository(lambda: Connection(path))


def write_fixture_csvs(root):
    folder = Path(root)/"data"
    folder.mkdir()
    for year in range(2022,2027):
        path = folder/f"{year}년도_정부광고집행내역_260930 기준.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=RAW_FIELDS)
            writer.writeheader()
            for start, amount in ((f"{year}0930", "100"), (f"{year}1001", "200"), ("날짜미확인", "300")):
                writer.writerow({"기관분류":"국가행정기관", "기관명":"시험기관", "매체구분":"인쇄", "매체명":"조선일보", "광고명":"검증용 광고", "광고료":amount,"수수료":"0", "총계(VAT포함)":amount, "광고시작일":start, "광고종료일":f"{year}1231"})
