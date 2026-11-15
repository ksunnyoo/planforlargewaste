"""수수료 계산기. 금액은 이 모듈(코드)만 계산하며 LLM은 금액을 만들지 않는다.

- fee_type이 free/exempt이면 소계 0원이며 화면은 "무료"/"면제"로 표시한다.
- 지자체 수수료와 업체 작업비는 항상 분리해서 반환한다.
"""
from dataclasses import dataclass
from typing import List, Optional

VALID_FEE_TYPES = ("paid", "free", "exempt")
MIN_QTY, MAX_QTY = 1, 99


class FeeCalculationError(ValueError):
    """입력 검증 오류(API에서는 VALIDATION_ERROR로 변환)."""


@dataclass(frozen=True)
class LineInput:
    unit_fee_won: int
    fee_type: str
    quantity: int
    operator_fee_won: int = 0


@dataclass(frozen=True)
class LineResult:
    unit_fee_won: int
    fee_type: str
    quantity: int
    municipal_fee_won: int
    operator_fee_won: int


@dataclass(frozen=True)
class Totals:
    municipal_fee_total_won: int
    operator_fee_total_won: int
    grand_total_won: int


def calculate_line(line: LineInput) -> LineResult:
    if line.fee_type not in VALID_FEE_TYPES:
        raise FeeCalculationError("알 수 없는 fee_type: " + str(line.fee_type))
    if isinstance(line.quantity, bool) or not isinstance(line.quantity, int):
        raise FeeCalculationError("수량은 정수여야 합니다.")
    if not (MIN_QTY <= line.quantity <= MAX_QTY):
        raise FeeCalculationError("수량은 1~99 범위여야 합니다.")
    if isinstance(line.unit_fee_won, bool) or not isinstance(line.unit_fee_won, int) or line.unit_fee_won < 0:
        raise FeeCalculationError("단가는 0 이상의 정수여야 합니다.")
    if line.fee_type == "paid" and line.unit_fee_won == 0:
        raise FeeCalculationError("유료 품목의 단가는 0원일 수 없습니다.")
    if line.fee_type in ("free", "exempt") and line.unit_fee_won != 0:
        raise FeeCalculationError("무료·면제 품목의 단가는 0원이어야 합니다.")
    if isinstance(line.operator_fee_won, bool) or not isinstance(line.operator_fee_won, int) or line.operator_fee_won < 0:
        raise FeeCalculationError("업체 작업비는 0 이상의 정수여야 합니다.")
    municipal = line.unit_fee_won * line.quantity
    return LineResult(line.unit_fee_won, line.fee_type, line.quantity, municipal, line.operator_fee_won)


def calculate(lines: List[LineInput]) -> "tuple[List[LineResult], Totals]":
    if not lines:
        raise FeeCalculationError("계산할 줄이 없습니다.")
    results = [calculate_line(x) for x in lines]
    municipal = sum(r.municipal_fee_won for r in results)
    operator = sum(r.operator_fee_won for r in results)
    return results, Totals(municipal, operator, municipal + operator)
