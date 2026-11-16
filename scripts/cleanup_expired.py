"""만료된 견적(expires_at 경과)을 삭제합니다. 줄·피드백은 견적과 함께 삭제됩니다(외래키 CASCADE).

사용(저장소 최상위 폴더에서):
  uv run --project backend python scripts/cleanup_expired.py            # 대상 개수만 출력(삭제하지 않음)
  uv run --project backend python scripts/cleanup_expired.py --apply    # 실제 삭제
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from load_to_db import read_env  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="지정하지 않으면 삭제하지 않고 개수만 보여 줍니다")
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
    with get_engine().begin() as c:
        n = c.execute(text("SELECT count(*) FROM estimates WHERE expires_at <= now()")).scalar()
        total = c.execute(text("SELECT count(*) FROM estimates")).scalar()
        print(f"전체 견적 {total}건 중 만료 {n}건")
        if a.apply and n:
            c.execute(text("DELETE FROM estimates WHERE expires_at <= now()"))
            print(f"삭제 완료: {n}건")
        elif n:
            print("삭제하려면 --apply를 붙이십시오.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
