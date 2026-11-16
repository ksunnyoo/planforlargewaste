"""임베딩·하이브리드 검색 시험. 실제 API·pgvector 없이 함수 단위로 확인한다."""
import pytest

from app.core import config
from app.services import embeddings, item_search
from app.services.item_search import rrf_fuse, search_items_mode


def c(i, score=0.5):
    return {"item_id": i, "score": score, "name": f"n{i}", "spec": "", "category": "", "fee_won": 0, "fee_type": "paid"}


def test_pgvector_문자열():
    assert embeddings.to_pgvector([0.5, -1, 2]) == "[0.5,-1,2]"


def test_RRF_양쪽에_있는_후보가_앞선다():
    out = rrf_fuse([c(1), c(2), c(3)], [c(3), c(4)], 10)
    assert [x["item_id"] for x in out][0] == 3
    assert {x["item_id"] for x in out} == {1, 2, 3, 4}


def test_RRF_표시_점수는_trigram_점수_우선():
    out = rrf_fuse([c(1, 0.9)], [c(1, 0.4)], 5)
    assert out[0]["score"] == 0.9


def test_RRF_개수_제한과_빈_입력():
    assert rrf_fuse([], [], 5) == []
    assert len(rrf_fuse([c(i) for i in range(1, 9)], [], 3)) == 3


def test_질의_임베딩_실패하면_trigram으로_저하(monkeypatch):
    monkeypatch.setattr(item_search, "search_items", lambda conn, code, q, n: [c(7, 0.8)])

    def boom(*a):
        raise embeddings.EmbeddingUnavailable("x")
    monkeypatch.setattr(item_search, "vector_search", boom)
    for mode in ("vector", "hybrid"):
        assert [x["item_id"] for x in search_items_mode(None, "3780000", "소파", 5, mode)] == [7]


def test_모드별_동작(monkeypatch):
    monkeypatch.setattr(item_search, "search_items", lambda conn, code, q, n: [c(1, 0.9), c(2, 0.6)])
    monkeypatch.setattr(item_search, "vector_search", lambda conn, code, q, n: [c(2, 0.7), c(3, 0.6)])
    ids = lambda mode: [x["item_id"] for x in search_items_mode(None, "3780000", "소파", 5, mode)]
    assert ids("trigram") == [1, 2]
    assert ids("vector") == [2, 3]
    assert ids("hybrid")[0] == 2 and set(ids("hybrid")) == {1, 2, 3}


def test_기본_설정은_trigram():
    assert config.Settings(_env_file=None).retrieval_mode == "trigram"


def test_질의_벡터는_차원을_확인하고_캐시된다():
    calls = []
    embeddings.set_embed_override(lambda t: calls.append(t) or [0.1] * 768)
    try:
        assert len(embeddings.embed_query("소파")) == 768
        embeddings.embed_query("소파")
        assert calls == ["소파"]
    finally:
        embeddings.set_embed_override(None)


def test_키_없으면_임베딩_불가(monkeypatch):
    monkeypatch.setattr(config.settings, "gemini_api_key", "")
    embeddings.set_embed_override(None)
    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.embed_query("키없음")
