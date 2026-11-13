"""정제된 CSV를 Postgres(Supabase)에 적재한다.

실행(저장소 최상위 폴더에서):
  uv run --project backend python scripts/load_to_db.py            # 빈 DB에 처음 적재
  uv run --project backend python scripts/load_to_db.py --reset    # 기존 데이터를 지우고 다시 적재

하는 일: db/schema.sql 실행 -> municipalities, item_catalog, waste_items 적재.
임베딩(item_catalog.embedding)은 비워 두며, 모델 확정 후 별도 스크립트로 채운다.
DATABASE_URL은 backend/.env 에서 읽는다(키·비밀번호는 화면에 출력하지 않는다).
"""
import argparse
import csv
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent


def read_env(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def clean_url(url):
    # SQLAlchemy 형식(postgresql+psycopg://)을 psycopg 형식으로 바꾼다.
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def copy_csv(cur, table, columns, csv_path, converters=None):
    converters = converters or {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
            n = 0
            for row in reader:
                values = []
                for c in columns:
                    v = row[c]
                    if c in converters:
                        v = converters[c](v)
                    values.append(v if v != "" else None)
                cp.write_row(values)
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="기존 데이터를 지우고 다시 적재")
    ap.add_argument("--data", default=str(ROOT / "data" / "processed"))
    a = ap.parse_args()

    url = read_env(ROOT / "backend" / ".env").get("DATABASE_URL", "")
    if not url:
        print("backend/.env 에 DATABASE_URL이 없습니다.")
        return 1
    data = Path(a.data)
    for name in ("municipalities.csv", "item_catalog.csv", "waste_items.csv"):
        if not (data / name).exists():
            print(f"{name} 이(가) 없습니다. 먼저 scripts/prepare_data.py 를 실행하십시오.")
            return 1

    boolean = lambda v: "t" if v.lower() == "true" else "f"
    with psycopg.connect(clean_url(url)) as conn:
        with conn.cursor() as cur:
            cur.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
            cur.execute("SELECT count(*) FROM waste_items")
            existing = cur.fetchone()[0]
            if existing and not a.reset:
                print(f"waste_items에 이미 {existing}행이 있습니다. 다시 적재하려면 --reset 을 붙이십시오.")
                return 1
            if a.reset:
                cur.execute("TRUNCATE waste_items, item_catalog, municipalities RESTART IDENTITY CASCADE")
            n1 = copy_csv(cur, "municipalities",
                          ["code", "name", "support_level", "procedure_supported", "spec_missing",
                           "data_base_date", "legal_effective_date", "item_count"],
                          data / "municipalities.csv",
                          {"procedure_supported": boolean, "spec_missing": boolean})
            n2 = copy_csv(cur, "item_catalog",
                          ["id", "name", "spec", "name_norm", "spec_norm", "search_text"],
                          data / "item_catalog.csv")
            n3 = copy_csv(cur, "waste_items",
                          ["municipality_code", "catalog_id", "category", "name", "spec",
                           "fee_won", "fee_type", "source_dataset", "base_date"],
                          data / "waste_items.csv")
        conn.commit()
    print(f"적재 완료: municipalities {n1}, item_catalog {n2}, waste_items {n3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
