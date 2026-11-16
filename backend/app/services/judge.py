"""충실도(Faithfulness) 판정: 답변의 모든 사실 주장이 인용 근거에서 확인되는지를 LLM으로 K회 판정해 다수결로 정한다.

서비스 요청 경로에서는 쓰지 않고 평가(eval/run_eval.py --judge K)에서만 쓴다.
한계: 답변을 만든 모델과 같은 계열 모델이 판정하면 자기 선호 편향이 있을 수 있어, 사람 표본 확인으로 보완한다.
"""
import json
import re
from typing import Callable, Dict, List, Optional

JUDGE_SYSTEM = (
    "당신은 답변이 근거 문단에 충실한지 판정하는 심사자입니다. 근거(evidence)와 답변(answer)만 비교합니다.\n"
    "규칙: (1) 답변의 모든 사실(날짜·시간·금액·전화번호·장소·절차·조건)이 근거에 명시되어 있으면 supported를 true로 함. "
    "(2) 근거에 없거나 근거와 다른 사실이 하나라도 있으면 false로 하고 unsupported_claims에 그 주장을 적음. "
    "(3) 일반 상식이나 추측으로 보충한 내용은 근거에 없는 것으로 봄. (4) 표현만 바꾼 것은 근거와 같은 의미이면 지지되는 것으로 봄.\n"
    '출력은 JSON 객체 하나만: {"supported":true,"unsupported_claims":[]}'
)


def parse_vote(text: str) -> Optional[bool]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    v = d.get("supported") if isinstance(d, dict) else None
    return v if isinstance(v, bool) else None


def judge_faithfulness(answer: str, evidence: List[str], k: int = 3,
                       invoke: Optional[Callable[[str, str], str]] = None) -> Dict:
    """반환: {"votes":[bool|None...], "supported": bool|None, "valid": int, "unanimous": bool|None}
    유효 표가 과반(k//2+1)에 못 미치면 supported는 None(판정 불가)."""
    if invoke is None:
        from app.services.llm import _invoke as invoke  # 지연 import: 시험에서 LLM 설정 불필요
    payload = json.dumps({"answer": answer, "evidence": evidence}, ensure_ascii=False)
    votes: List[Optional[bool]] = []
    for _ in range(k):
        try:
            votes.append(parse_vote(invoke(JUDGE_SYSTEM, payload)))
        except Exception:  # 한도·네트워크 오류는 그 표만 무효 처리
            votes.append(None)
    valid = [v for v in votes if v is not None]
    need = k // 2 + 1
    if len(valid) < need:
        return {"votes": votes, "supported": None, "valid": len(valid), "unanimous": None}
    yes = sum(1 for v in valid if v)
    supported = yes >= need if yes != len(valid) - yes else False  # 동수면 지지되지 않은 것으로 봄(보수적)
    return {"votes": votes, "supported": supported, "valid": len(valid), "unanimous": len(set(valid)) == 1}
