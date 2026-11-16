from app.services.judge import judge_faithfulness, parse_vote


def seq(*outs):
    it = iter(outs)

    def f(system, payload):
        v = next(it)
        if isinstance(v, Exception):
            raise v
        return v
    return f


Y = '{"supported": true, "unsupported_claims": []}'
N = '{"supported": false, "unsupported_claims": ["x"]}'


def test_파싱():
    assert parse_vote("설명 " + Y) is True and parse_vote(N) is False
    assert parse_vote("json 아님") is None and parse_vote('{"supported": "yes"}') is None


def test_다수결():
    r = judge_faithfulness("답", ["근거"], 3, seq(Y, Y, N))
    assert r["supported"] is True and r["unanimous"] is False
    assert judge_faithfulness("답", ["근거"], 3, seq(N, N, Y))["supported"] is False
    assert judge_faithfulness("답", ["근거"], 3, seq(Y, Y, Y))["unanimous"] is True


def test_무효_표_처리():
    r = judge_faithfulness("답", ["근거"], 3, seq(Y, RuntimeError("x"), "형식오류"))
    assert r["supported"] is None and r["valid"] == 1
    r = judge_faithfulness("답", ["근거"], 3, seq(Y, Y, RuntimeError("x")))
    assert r["supported"] is True and r["valid"] == 2


def test_동수는_지지되지_않음():
    assert judge_faithfulness("답", ["근거"], 4, seq(Y, Y, N, N))["supported"] is False
