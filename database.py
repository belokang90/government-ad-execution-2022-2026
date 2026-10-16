"""웹 API와 CSV 적재 스크립트가 공유하는 MySQL 연결 함수."""

import pymysql

from config import DB_CONFIG


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
