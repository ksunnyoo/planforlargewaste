"""절차 안내문(마크다운)을 청크로 나눠 procedure_chunks에 적재한다.

실행(저장소 최상위 폴더에서):
  uv run --project backend python scripts/load_procedure.py
  (load_to_db.py --reset 을 실행한 뒤에는 이 스크립트가 자동으로 함께 실행된다)

- 입력: data/raw/seongnam_procedure.md (사용자가 복사해 보관한 성남시 안내문)
- 청크 규칙: "## " 제목 단위. 짧은 "대상"과 "신고의무자"는 하나로 합친다.
- 같은 지자체의 기존 청크는 지우고 다시 넣는다. 임베딩은 비워 둔다(소량이라 키워드 검색 사용).
- base_date가 날짜 형식이 아니면(예: "미확인") NULL로 저장한다.
"""
import re
import sys
from datetime import date
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
SEONGNAM = "3780000"
MERGE = {"대상": "대상·신고의무자", "신고의무자": "대상·신고의무자"}
RENAME = {"대형폐가전 무상 방문 수거 사업 시행": "대형폐가전 무상 방문 수거"}


def parse(md: str):
    meta, body = {}, md
    m = re.match(r"---\n(.*?)\n---\n", md, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = md[m.end():]
    sections = []
    for part in re.split(r"^## ", body, flags=re.M)[1:]:
        title, _, content = part.partition("\n")
        title, content = title.strip(), content.strip()
        name = RENAME.get(title, MERGE.get(title, title))
        if sections and sections[-1][0] == name:
            sections[-1] = (name, sections[-1][1] + "\n" + title + ": " + content)
        elif name != title and title in MERGE:
            sections.append((name, title + ": " + content))
        else:
            sections.append((name, content))
    return meta, sections


def parse_date(s: str):
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def load(cur, code: str = SEONGNAM, path: Path = ROOT / "data" / "raw" / "seongnam_procedure.md") -> int:
    meta, sections = parse(path.read_text(encoding="utf-8"))
    cur.execute("DELETE FROM procedure_chunks WHERE municipality_code = %s", (code,))
    base = parse_date(meta.get("base_date", ""))
    for name, content in sections:
        cur.execute(
            "INSERT INTO procedure_chunks (municipality_code, source_name, section, content, base_date)"
            " VALUES (%s, %s, %s, %s, %s)",
            (code, meta.get("source_name", "성남시 대형폐기물 배출 안내"), name, content, base))
    return len(sections)


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from load_to_db import clean_url, read_env
    url = read_env(ROOT / "backend" / ".env").get("DATABASE_URL", "")
    if not url:
        print("backend/.env 에 DATABASE_URL이 없습니다.")
        return 1
    with psycopg.connect(clean_url(url)) as conn:
        with conn.cursor() as cur:
            n = load(cur)
        conn.commit()
    print(f"절차 청크 적재 완료: {n}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
