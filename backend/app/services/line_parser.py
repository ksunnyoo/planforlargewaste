"""입력 텍스트를 줄로 나누고 수량을 뽑는다(규칙 기반, LLM 미사용).

- 구분: 줄바꿈, 쉼표, 슬래시, 가운뎃점, 세미콜론, "및/그리고", 단어 뒤 "랑/이랑/하고".
- 수량: "4개", "2대", "세트", "x3", "두 개" 등. 규격 숫자("3인용", "300ℓ", "180x60")는 수량으로 보지 않는다.
- 수량은 1~99. 범위를 넘으면 99로 줄이고 안내 문구를 남긴다.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

MAX_LINES = 30
MIN_QTY, MAX_QTY = 1, 99

_SPLIT = re.compile(r"[\n\r,，/·;；]+|\s+(?:및|그리고)\s+|(?<=[가-힣])(?:이랑|랑|하고)\s+")
_NUM_UNIT = re.compile(r"(\d+)\s*(?:개|세트|짝|EA|ea|pcs)|(\d+)\s*(?:대|장|벌|점)(?![가-힣])")
_X_QTY = re.compile(r"(?:^|\s)[x×X]\s*(\d{1,3})(?=\s|$)")
_KO_NUM = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4,
           "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_KO_QTY = re.compile(r"(한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:개|대|세트|짝)")


@dataclass(frozen=True)
class ParsedLine:
    line_no: int
    raw_text: str
    query: str          # 수량 표현을 뺀 검색어
    quantity: int
    note: Optional[str] = None


def split_lines(text: str) -> List[str]:
    parts = [p.strip() for p in _SPLIT.split(text)]
    return [p for p in parts if p]


def extract_quantity(raw: str) -> "tuple[str, int, Optional[str]]":
    """(수량 표현을 뺀 문자열, 수량, 안내문구)."""
    qty, note, cleaned = 1, None, raw
    m = _NUM_UNIT.search(raw)
    if m:
        qty = int(m.group(1) or m.group(2))
        cleaned = raw[: m.start()] + " " + raw[m.end():]
    else:
        m = _KO_QTY.search(raw)
        if m:
            qty = _KO_NUM[m.group(1)]
            cleaned = raw[: m.start()] + " " + raw[m.end():]
        else:
            m = _X_QTY.search(raw)
            if m:
                qty = int(m.group(1))
                cleaned = raw[: m.start()] + " " + raw[m.end():]
    if qty > MAX_QTY:
        qty, note = MAX_QTY, "수량은 최대 99개까지 입력할 수 있어 99개로 조정했습니다."
    elif qty < MIN_QTY:
        qty, note = MIN_QTY, "수량은 1개 이상이어야 해서 1개로 조정했습니다."
    return re.sub(r"\s+", " ", cleaned).strip(), qty, note


def parse_lines(text: str) -> List[ParsedLine]:
    out: List[ParsedLine] = []
    for i, raw in enumerate(split_lines(text), start=1):
        query, qty, note = extract_quantity(raw)
        out.append(ParsedLine(i, raw, query, qty, note))
    return out
