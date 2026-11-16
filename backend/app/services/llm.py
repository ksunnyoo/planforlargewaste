"""LLM 호출(품목 후보 중 선택). Gemini 우선, 실패 시 Groq. 금액은 LLM에 맡기지 않는다.

LLM은 서버가 준 후보 번호 중에서만 고르고, 이유 한 문장을 쓴다. 후보 밖 번호나 형식 오류는 버린다.
테스트에서는 set_llm_override()로 가짜 함수를 넣는다.
"""
import json
import re
from typing import Callable, Dict, List, Optional

from app.core import config

# 입력: [{"line_no", "text", "options":[{"n","name","spec"}]}] → 출력: {line_no: {"n": 번호 또는 None, "reason": str}}
LlmFn = Callable[[List[dict]], Dict[int, dict]]
_override: Optional[LlmFn] = None


class LlmUnavailable(Exception):
    pass


def set_llm_override(fn: Optional[LlmFn]) -> None:
    global _override
    _override = fn


SYSTEM = (
    "당신은 대형폐기물 품목 매칭 도우미입니다. 각 줄의 입력 문구에 가장 맞는 후보 번호(n)를 고릅니다.\n"
    "규칙: 후보 목록에 있는 번호만 선택합니다. 확실하지 않으면 n을 null로 둡니다. "
    "금액·수수료는 언급하지 않습니다. reason은 한국어 한 문장(40자 이내)입니다.\n"
    '출력은 JSON 배열만: [{"line_no":1,"n":2,"reason":"..."}]'
)


def _build_chain():
    s = config.settings
    models = []
    if s.gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        models.append(ChatGoogleGenerativeAI(model=s.gemini_model, google_api_key=s.gemini_api_key,
                                             temperature=0, timeout=s.llm_timeout_seconds, max_retries=0))
    if s.groq_api_key:
        from langchain_groq import ChatGroq
        models.append(ChatGroq(model=s.groq_model, api_key=s.groq_api_key, temperature=0,
                               timeout=s.llm_timeout_seconds, max_retries=0))
    if not models:
        raise LlmUnavailable("LLM 키가 설정되지 않았습니다.")
    return models[0].with_fallbacks(models[1:]) if len(models) > 1 else models[0]


def _parse(text: str) -> List[dict]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        raise LlmUnavailable("응답 형식 오류")
    try:
        data = json.loads(m.group(0))
    except ValueError as e:
        raise LlmUnavailable("응답 형식 오류") from e
    return [d for d in data if isinstance(d, dict)]


def choose_candidates(batch: List[dict]) -> Dict[int, dict]:
    if _override is not None:
        return _override(batch)
    payload = json.dumps(batch, ensure_ascii=False)
    try:
        chain = _build_chain()
        resp = chain.invoke([("system", SYSTEM), ("human", payload)])
    except LlmUnavailable:
        raise
    except Exception as e:  # 네트워크·한도·모델명 오류 등
        raise LlmUnavailable(type(e).__name__) from e
    content = resp.content if isinstance(resp.content, str) else str(resp.content)
    out: Dict[int, dict] = {}
    for d in _parse(content):
        ln, n = d.get("line_no"), d.get("n")
        if isinstance(ln, int) and (n is None or isinstance(n, int)):
            out[ln] = {"n": n, "reason": str(d.get("reason") or "")[:80]}
    return out
