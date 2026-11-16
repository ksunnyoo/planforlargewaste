"""LLM 키·모델명 확인용. 실제로 1~2회 호출합니다(무료 한도 소량 사용).

실행(backend 폴더에서): uv run python ../scripts/llm_smoke.py
키 값은 출력하지 않습니다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import settings  # noqa: E402


def try_model(label, build):
    try:
        m = build()
        r = m.invoke("한 단어로만 답하십시오: 소파는 가구입니까?")
        print("[OK ]", label, "->", str(r.content)[:40].replace("\n", " "))
    except Exception as e:
        print("[실패]", label, type(e).__name__, str(e)[:160].replace("\n", " "))


if settings.gemini_api_key:
    from langchain_google_genai import ChatGoogleGenerativeAI
    try_model("Gemini " + settings.gemini_model, lambda: ChatGoogleGenerativeAI(
        model=settings.gemini_model, google_api_key=settings.gemini_api_key, max_retries=0, timeout=15))
else:
    print("[건너뜀] GEMINI_API_KEY 없음")
if settings.groq_api_key:
    from langchain_groq import ChatGroq
    try_model("Groq " + settings.groq_model, lambda: ChatGroq(
        model=settings.groq_model, api_key=settings.groq_api_key, max_retries=0, timeout=15))
else:
    print("[건너뜀] GROQ_API_KEY 없음")
