"""품목 카탈로그(item_catalog.search_text)의 임베딩을 만들어 DB에 저장합니다. 중단해도 이어서 실행할 수 있습니다.

사용(저장소 최상위 폴더에서):
  uv run --project backend python scripts/build_embeddings.py --check
  uv run --project backend python scripts/build_embeddings.py --count
  uv run --project backend python scripts/build_embeddings.py --municipality 3780000 --municipality <다른 코드>
  uv run --project backend python scripts/build_embeddings.py            # 전체(무료 일일 한도에 걸리면 멈추고, 다시 실행하면 이어서 진행)

--municipality 를 주면 그 지자체의 품목만 대상으로 합니다(무료 한도 절약).
키 값은 출력하지 않습니다. 모델·차원은 backend/.env의 EMBEDDING_MODEL, config의 embedding_dim(768)을 따릅니다.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from load_to_db import read_env  # noqa: E402


def setup():
    from app.core import config
    env = read_env(ROOT / "backend" / ".env")
    for k in ("database_url", "gemini_api_key", "embedding_model"):
        if env.get(k.upper()):
            setattr(config.settings, k, env[k.upper()])
    return config.settings


def targets_sql(codes):
    where = "c.embedding IS NULL"
    if codes:
        where += " AND EXISTS (SELECT 1 FROM waste_items wi WHERE wi.catalog_id = c.id AND wi.municipality_code = ANY(:codes))"
    return where


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="임베딩 1회 호출로 모델명·차원만 확인")
    ap.add_argument("--count", action="store_true", help="대상 개수만 출력")
    ap.add_argument("--municipality", action="append", default=[], help="지자체 코드(여러 번 지정 가능)")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=30.0, help="배치 사이 대기(초)")
    a = ap.parse_args()
    s = setup()
    from app.services import embeddings

    if a.check:
        if not s.gemini_api_key:
            print("GEMINI_API_KEY가 backend/.env에 없습니다.")
            return 1
        try:
            v = embeddings.embed_documents(["소파"])[0]
            print(f"[OK ] {s.embedding_model} 차원 {len(v)}")
            return 0
        except Exception as e:
            print("[실패]", type(e).__name__, str(e)[:200].replace("\n", " "))
            return 1

    if not s.database_url:
        print("backend/.env에 DATABASE_URL이 없습니다.")
        return 1
    from sqlalchemy import text
    from app.core.database import get_engine
    eng = get_engine()
    params = {"codes": a.municipality} if a.municipality else {}
    where = targets_sql(a.municipality)
    with eng.connect() as c:
        total = c.execute(text("SELECT count(*) FROM item_catalog"), {}).scalar()
        todo = c.execute(text(f"SELECT count(*) FROM item_catalog c WHERE {where}"), params).scalar()
        chars = c.execute(text(f"SELECT coalesce(sum(length(search_text)),0) FROM item_catalog c WHERE {where}"), params).scalar()
    print(f"카탈로그 {total}건 중 임베딩 대상 {todo}건(글자 수 합 {chars}).")
    if a.count or not todo:
        return 0
    if not s.gemini_api_key:
        print("GEMINI_API_KEY가 backend/.env에 없습니다.")
        return 1

    done = 0
    while True:
        with eng.connect() as c:
            rows = c.execute(text(f"SELECT c.id, c.search_text FROM item_catalog c WHERE {where} ORDER BY c.id LIMIT :n"),
                             dict(params, n=a.batch)).all()
        if not rows:
            break
        try:
            vecs = None
            for attempt in range(6):
                try:
                    vecs = embeddings.embed_documents([r[1] for r in rows])
                    break
                except Exception as e:
                    msg = str(e)
                    if "PerMinute" in msg or "per minute" in msg:  # 분당 한도: 기다렸다가 같은 배치를 다시 시도
                        print(f"분당 한도: 50초 대기 후 재시도({attempt + 1}/6)", flush=True)
                        time.sleep(50)
                        continue
                    raise
            if vecs is None:
                raise RuntimeError("분당 한도 재시도 6회 실패")
        except Exception as e:
            print(f"중단: {type(e).__name__} {str(e)[:1500]!r}. 지금까지 {done}건 저장. 한도가 풀린 뒤 같은 명령을 다시 실행하면 이어서 진행합니다.")
            return 2
        with eng.begin() as c:
            for (cid, _), v in zip(rows, vecs):
                c.execute(text("UPDATE item_catalog SET embedding = CAST(:v AS vector) WHERE id = :i"),
                          {"v": embeddings.to_pgvector(v), "i": cid})
        done += len(rows)
        print(f"{done}/{todo}", flush=True)
        time.sleep(a.sleep)
    print("완료:", done, "건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
