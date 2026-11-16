"""모든 시험 공통: 실제 LLM을 호출하지 않고, 요청 제한 카운터를 시험마다 초기화한다."""
import pytest

from app.services import usage
from app.services.llm import set_llm_override, set_procedure_override, set_qa_override


def fake_procedure(payload):
    """근거 청크 id만 인용하는 정상 응답(숫자 없음)."""
    ids = [c["id"] for c in payload["chunks"]]
    return {"steps": [{"title": "배출 신고", "detail": "안내문에 따라 배출을 신고합니다.", "citation_ids": ids[:1]},
                      {"title": "수거", "detail": "신고 후 안내에 따라 배출합니다.", "citation_ids": ids[:2]}],
            "checklist": [{"text": "신고 후 배출하십시오.", "citation_ids": ids[:1]}]}


@pytest.fixture(autouse=True)
def _isolate_llm_and_limits():
    usage.reset_for_tests()
    set_llm_override(lambda batch: {})
    set_procedure_override(fake_procedure)
    set_qa_override(lambda p: {"answerable": False})
    yield
    set_llm_override(None)
    set_procedure_override(None)
    set_qa_override(None)
    usage.reset_for_tests()
