"""임베딩 클라이언트(Gemini). 색인(scripts/build_embeddings.py)과 질의에서 같은 모델·차원을 쓴다.

질의 임베딩이 실패하면 EmbeddingUnavailable을 내고, 호출하는 쪽이 trigram 검색으로 저하 동작한다.
"""
from functools import lru_cache
from typing import Callable, List, Optional

from app.core import config


class EmbeddingUnavailable(Exception):
    pass


_override: Optional[Callable[[str], List[float]]] = None


def set_embed_override(fn):
    """시험용: 실제 API 대신 쓸 함수(문자열 → 벡터)를 지정."""
    global _override
    _override = fn
    _query_vector.cache_clear()


def _client():
    s = config.settings
    if not s.gemini_api_key:
        raise EmbeddingUnavailable("GEMINI_API_KEY 없음")
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=s.embedding_model or "gemini-embedding-001", google_api_key=s.gemini_api_key)


def to_pgvector(vec: List[float]) -> str:
    return "[" + ",".join(f"{float(x):.7g}" for x in vec) + "]"


@lru_cache(maxsize=512)
def _query_vector(text: str) -> tuple:
    if _override is not None:
        return tuple(_override(text))
    try:
        v = _client().embed_query(text, task_type="RETRIEVAL_QUERY", output_dimensionality=config.settings.embedding_dim)
    except EmbeddingUnavailable:
        raise
    except Exception as e:  # 네트워크·한도·모델명 오류 모두 저하 동작 대상
        raise EmbeddingUnavailable(type(e).__name__) from e
    if len(v) != config.settings.embedding_dim:
        raise EmbeddingUnavailable(f"차원 불일치: {len(v)}")
    return tuple(v)


def embed_query(text: str) -> List[float]:
    return list(_query_vector(text))


def embed_documents(texts: List[str]) -> List[List[float]]:
    """색인용(스크립트에서만 사용). 실패하면 예외를 그대로 낸다."""
    s = config.settings
    vs = _client().embed_documents(texts, task_type="RETRIEVAL_DOCUMENT", output_dimensionality=s.embedding_dim)
    if any(len(v) != s.embedding_dim for v in vs):
        raise EmbeddingUnavailable("차원 불일치")
    return vs
