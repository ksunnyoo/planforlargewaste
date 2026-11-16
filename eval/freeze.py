"""평가 동결 기록: 검증용(test) 측정 전에 코드·평가셋 상태를 고정하고, 측정 때 그대로인지 확인한다.

기록 파일: eval/freeze.json (커밋하십시오)
  - 평가에 영향을 주는 코드 파일과 평가셋 파일의 sha256
  - 기록 시점의 git 커밋(참고용), 기록 시각, 메모
검증용 측정은 기록이 없거나 파일 내용이 기록과 다르면 시작하지 않습니다.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

# 검색·매칭·절차·판정·평가 결과에 영향을 주는 파일(상대 경로)
CODE_FILES = [
    "backend/app/services/matcher.py",
    "backend/app/services/item_search.py",
    "backend/app/services/embeddings.py",
    "backend/app/services/llm.py",
    "backend/app/services/judge.py",
    "backend/app/services/procedure.py",
    "backend/app/core/config.py",
    "eval/run_eval.py",
]
DATA_FILES = ["eval/datasets/v1/matching.jsonl", "eval/datasets/v1/procedure.jsonl"]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_state(root: Path) -> dict:
    files = {}
    for rel in CODE_FILES + DATA_FILES:
        p = root / rel
        files[rel] = sha256_of(p) if p.exists() else None
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True).strip()
    except Exception:
        commit = "unknown"
    return {"git_commit": commit, "files": files}


def write_freeze(root: Path, note: str = "") -> dict:
    st = current_state(root)
    st["frozen_at"] = datetime.now(KST).isoformat(timespec="seconds")
    st["note"] = note
    (root / "eval" / "freeze.json").write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    return st


def check_freeze(root: Path) -> tuple:
    """(통과 여부, 사유 목록)을 돌려준다."""
    path = root / "eval" / "freeze.json"
    if not path.exists():
        return False, ["동결 기록(eval/freeze.json)이 없습니다. 먼저 --freeze 로 기록하십시오."]
    saved = json.loads(path.read_text(encoding="utf-8"))
    now = current_state(root)["files"]
    reasons = []
    for rel, h in saved.get("files", {}).items():
        if now.get(rel) != h:
            reasons.append(f"동결 후 바뀐 파일: {rel}")
    for rel in now:
        if rel not in saved.get("files", {}):
            reasons.append(f"동결 기록에 없는 파일: {rel}")
    return (not reasons), reasons
