import pytest
from app.services.fee_calculator import FeeCalculationError, LineInput, calculate


def test_다품목_합계_PRD_F05():
    # PRD F-05: 5,000원x2, 10,000원x1 -> 20,000원
    _, t = calculate([LineInput(5000, "paid", 2), LineInput(10000, "paid", 1)])
    assert t.municipal_fee_total_won == 20000


def test_API예시_합계_분리():
    # API 정의서 예시: 10,000 + 5,000 + 3,000x4 = 27,000 / 작업비 30,000 / 총 57,000
    lines = [LineInput(10000, "paid", 1, 30000), LineInput(5000, "paid", 1), LineInput(3000, "paid", 4)]
    results, t = calculate(lines)
    assert [r.municipal_fee_won for r in results] == [10000, 5000, 12000]
    assert (t.municipal_fee_total_won, t.operator_fee_total_won, t.grand_total_won) == (27000, 30000, 57000)


def test_면제와_무료는_0원_유료만_합산():
    results, t = calculate([LineInput(0, "exempt", 1), LineInput(0, "free", 3), LineInput(5000, "paid", 1)])
    assert t.municipal_fee_total_won == 5000
    assert [r.fee_type for r in results] == ["exempt", "free", "paid"]


@pytest.mark.parametrize("qty", [1, 99])
def test_수량_경계_허용(qty):
    calculate([LineInput(1000, "paid", qty)])


@pytest.mark.parametrize("qty", [0, 100, -1])
def test_수량_범위_밖_거부(qty):
    with pytest.raises(FeeCalculationError):
        calculate([LineInput(1000, "paid", qty)])


def test_유료_0원_거부():
    with pytest.raises(FeeCalculationError):
        calculate([LineInput(0, "paid", 1)])


def test_무료인데_금액이_있으면_거부():
    with pytest.raises(FeeCalculationError):
        calculate([LineInput(1000, "exempt", 1)])


def test_알수없는_유형_거부():
    with pytest.raises(FeeCalculationError):
        calculate([LineInput(1000, "other", 1)])


def test_빈_목록_거부():
    with pytest.raises(FeeCalculationError):
        calculate([])


def test_작업비_음수_거부():
    with pytest.raises(FeeCalculationError):
        calculate([LineInput(1000, "paid", 1, -1)])
