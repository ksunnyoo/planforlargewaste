"""접수된 피드백을 평가셋 보강 후보(JSONL)로 내보냅니다. 평가셋은 자동으로 바꾸지 않습니다.

각 줄: 피드백 유형·의견, 해당 견적 줄의 입력 문구와 선택된 품목, 제안 품목(있으면).
사용(저장소 최상위 폴더에서):
  uv run --project backend python scripts/export_feedback.py             # 화면에 요약 출력
  uv run --project backend python scripts/export_feedback.py --out eval/feedback_candidates.jsonl
내보낸 사례를 평가셋에 넣을 때는 사람이 정답을 확인하고 새 버전(v2)으로 올리며 CHANGELOG에 기록합니다.
개인정보가 섞였을 수 있으니 의견(comment)을 확인한 뒤 사용하십시오.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from load_to_db import read_env  # noqa: E402

SQL = """
SELECT f.id, f.type, f.comment, f.line_no, f.created_at, e.municipality_code, e.input_text,
       l.raw_text, wi.name AS item_name, wi.spec AS item_spec,
       sw.name AS suggested_name, sw.spec AS suggested_spec
FROM feedback f
JOIN estimates e ON e.id = f.estimate_id
LEFT JOIN estimate_lines l ON l.estimate_id = f.estimate_id AND l.line_no = f.line_no
LEFT JOIN waste_items wi ON wi.id = l.item_id
LEFT JOIN waste_items sw ON sw.id = f.suggested_item_id
ORDER BY f.id
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="JSONL 저장 경로(생략하면 화면 출력만)")
    a = ap.parse_args()
    from app.core import config
    env = read_env(ROOT / "backend" / ".env")
    if env.get("DATABASE_URL"):
        config.settings.database_url = env["DATABASE_URL"]
    if not config.settings.database_url:
        print("backend/.env에 DATABASE_URL이 없습니다.")
        return 1
    from sqlalchemy import text
    from app.core.database import get_engine
    with get_engine().connect() as c:
        rows = [dict(r) for r in c.execute(text(SQL)).mappings().all()]
    print(f"피드백 {len(rows)}건")
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        print(f"- #{r['id']} [{r['type']}] 줄 {r['line_no']}: 입력 {r['raw_text']!r} → {r['item_name']} {r['item_spec']}"
              + (f" / 제안 {r['suggested_name']} {r['suggested_spec']}" if r["suggested_name"] else "")
              + (f" / 의견 {r['comment']!r}" if r["comment"] else ""))
    if a.out:
        Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print("저장:", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
