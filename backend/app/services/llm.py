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
    "(1) 입력에 규격·크기·인원수·용량·단수 등 규격을 정할 단서가 없고 후보들이 규격만 다르면 규격을 임의로 고르지 말고 n을 null로 둡니다. "
    "(2) 후보가 입력과 다른 종류의 물건이면(예: 제습기와 가습기) n을 null로 둡니다. "
    "(3) 입력이 품목과 규격을 모두 특정하거나, 같은 종류의 후보가 규격 구분 없이 하나뿐일 때만 번호를 고릅니다. "
    "금액·수수료는 언급하지 않습니다. reason은 한국어 한 문장(40자 이내)입니다.\n"
    '출력은 JSON 배열만: [{"line_no":1,"n":2,"reason":"..."}]'
)


def _build_chain():
    s = config.settings
    models = []
    if s.gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        models.append(ChatGoogleGenerativeAI(model=s.gemini_model, google_api_key=s.gemini_api_key,
                                             timeout=s.llm_timeout_seconds, max_retries=0))
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


def _as_text(content) -> str:
    """Gemini는 content를 [{'type':'text','text':...}] 목록으로 줄 수 있어 글자만 이어 붙인다."""
    if isinstance(content, str):
        return content
    parts = []
    for c in content or []:
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, dict) and isinstance(c.get("text"), str):
            parts.append(c["text"])
    return "".join(parts)


def _invoke(system: str, payload: str) -> str:
    try:
        chain = _build_chain()
        resp = chain.invoke([("system", system), ("human", payload)])
    except LlmUnavailable:
        raise
    except Exception as e:  # 네트워크·한도·모델명 오류 등
        raise LlmUnavailable(type(e).__name__) from e
    return _as_text(resp.content)


def choose_candidates(batch: List[dict]) -> Dict[int, dict]:
    if _override is not None:
        return _override(batch)
    content = _invoke(SYSTEM, json.dumps(batch, ensure_ascii=False))
    out: Dict[int, dict] = {}
    for d in _parse(content):
        ln, n = d.get("line_no"), d.get("n")
        if isinstance(ln, int) and (n is None or isinstance(n, int)):
            out[ln] = {"n": n, "reason": str(d.get("reason") or "")[:80]}
    return out


# ---- 절차 안내 생성 ----
ProcFn = Callable[[dict], dict]
_proc_override: Optional[ProcFn] = None


def set_procedure_override(fn: Optional[ProcFn]) -> None:
    global _proc_override
    _proc_override = fn


PROC_SYSTEM = (
    "당신은 지자체 대형폐기물 배출 안내문을 정리하는 도우미입니다. 제공된 근거 문단(chunks)에 있는 내용만 사용합니다.\n"
    "규칙: (1) 근거에 없는 내용·추측 금지. (2) 날짜·시간·금액·전화번호·URL은 근거에 있는 값만 그대로 사용. "
    "(3) steps는 3~6개, 각 항목에 title(짧게), detail(한두 문장), citation_ids(근거 id 목록, 1개 이상)를 넣음. "
    "(4) checklist는 0~5개, 각 항목에 text와 citation_ids를 넣음. "
    "(5) 문장은 공공기관 안내문의 하십시오체로 씀. (6) notes에 적힌 조건은 반영하되 근거에 없는 내용은 만들지 않음.\n"
    '출력은 JSON 객체 하나만: {"steps":[{"title":"","detail":"","citation_ids":[1]}],'
    '"checklist":[{"text":"","citation_ids":[1]}]}'
)


def generate_procedure(payload: dict) -> dict:
    """payload: {"chunks":[{"id","section","content"}], "notes":[str]} → {"steps":[...],"checklist":[...]}"""
    if _proc_override is not None:
        return _proc_override(payload)
    content = _invoke(PROC_SYSTEM, json.dumps(payload, ensure_ascii=False))
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise LlmUnavailable("응답 형식 오류")
    try:
        data = json.loads(m.group(0))
    except ValueError as e:
        raise LlmUnavailable("응답 형식 오류") from e
    if not isinstance(data, dict):
        raise LlmUnavailable("응답 형식 오류")
    return data


# ---- 절차 질문(QA) ----
QaFn = Callable[[dict], dict]
_qa_override: Optional[QaFn] = None


def set_qa_override(fn: Optional[QaFn]) -> None:
    global _qa_override
    _qa_override = fn


QA_SYSTEM = (
    "당신은 지자체 대형폐기물 배출 안내문에 근거해 질문에 답하는 도우미입니다. 제공된 근거 문단(chunks)에 있는 내용만 사용합니다.\n"
    "규칙: (1) 근거에서 답을 확인할 수 있으면 answerable을 true로 하고, 한두 문장의 하십시오체로 답하며 citation_ids에 사용한 근거 id를 넣음. "
    "(2) 근거에 답이 없으면 answerable을 false로 하고 answer는 빈 문자열. 추측·일반 상식으로 답하지 않음. "
    "(3) 날짜·시간·금액·전화번호·URL은 근거에 있는 값만 그대로 사용.\n"
    '출력은 JSON 객체 하나만: {"answerable":true,"answer":"","citation_ids":[1]}'
)


def generate_answer(payload: dict) -> dict:
    """payload: {"question": str, "chunks":[{"id","section","content"}]}"""
    if _qa_override is not None:
        return _qa_override(payload)
    content = _invoke(QA_SYSTEM, json.dumps(payload, ensure_ascii=False))
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        raise LlmUnavailable("응답 형식 오류")
    try:
        data = json.loads(m.group(0))
    except ValueError as e:
        raise LlmUnavailable("응답 형식 오류") from e
    if not isinstance(data, dict):
        raise LlmUnavailable("응답 형식 오류")
    return data
