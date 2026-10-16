"""연도별 CSV를 MySQL에 추가 적재한다. 재실행하면 중복될 수 있다."""

import sys
from pathlib import Path

import pandas as pd

# python data/load_all_years.py 로 실행해도 루트의 공통 설정을 읽는다.
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
from database import get_db

conn = get_db()

target_files = {
    "2026년도_정부광고집행내역_260930 기준.csv": "2026",
    "2025년도_정부광고집행내역_260930 기준.csv": "2025",
    "2024년도_정부광고집행내역_260930 기준.csv": "2024",
    "2023년도_정부광고집행내역_260930 기준.csv": "2023",
    "2022년도_정부광고집행내역_260930 기준.csv": "2022"
}

with conn.cursor() as cur:
    # 💡 만약 기존 데이터를 싹 지우고 새로 넣으려면 아래 주석을 해제하세요
    # cur.execute("TRUNCATE TABLE ad_execution")
    
    for filename, year_str in target_files.items():
        file_path = BASE / filename
        if not file_path.exists():
            print(f"⚠️ [파일 없음] '{filename}' 파일이 없습니다. 건너뜁니다.")
            continue
        
        print(f"\n📂 [{year_str}년] '{filename}' 파일 읽는 중...")
        try:
            df = pd.read_csv(file_path, encoding="utf-8")
        except Exception as e:
            print(f"❌ 읽기 실패 ({filename}): {e}")
            continue

        print(f"🔄 총 {len(df):,}건 전처리 및 고속 적재 시작...")
        
        # 텍스트 컬럼 전처리 (광고시작일, 광고종료일 추가)
        for col in ['기관분류', '기관명', '매체구분', '매체명', '광고명', '광고시작일', '광고종료일']:
            if col not in df.columns:
                df[col] = ''
            df[col] = df[col].fillna('').astype(str)

        # 금액 컬럼 전처리
        for col in ['광고료', '수수료', '총계(VAT포함)']:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)

        # 튜플 바인딩에 광고시작일, 광고종료일 포함
        batch_values = list(zip(
            df['기관분류'],
            df['기관명'],
            df['매체구분'],
            df['매체명'],
            df['광고명'],
            df['광고시작일'],   # 👈 추가
            df['광고종료일'],   # 👈 추가
            df['광고료'],
            df['수수료'],
            df['총계(VAT포함)'],
            [f"{year_str}-01"] * len(df),
            [year_str] * len(df)
        ))

        sql = """
            INSERT INTO ad_execution (기관분류, 기관명, 매체구분, 매체명, 광고명, 광고시작일, 광고종료일, 광고료, 수수료, `총계(VAT포함)`, 집행년월, 집행연도)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        chunk_size = 10000
        for i in range(0, len(batch_values), chunk_size):
            chunk = batch_values[i:i + chunk_size]
            cur.executemany(sql, chunk)
            conn.commit()

        print(f"✨ [{year_str}년] 적재 완료! (총 {len(batch_values):,}건)")

conn.close()
print("\n🎉 모든 작업 완료!")