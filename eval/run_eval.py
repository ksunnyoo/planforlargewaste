"""평가 실행: 평가셋을 현재 코드로 돌려 지표·신뢰구간을 계산하고 eval/runs/ 에 원본을 저장한다.

실행(저장소 최상위 폴더에서, 예시):
  uv run --project backend python eval/run_eval.py --config C0 --split dev
  uv run --project backend python eval/run_eval.py --config C3 --split dev --repeat 1 --sleep 4

구성(LLM 없는 구성은 검색 지표만 의미가 큼):
  C0 trigram / C1 벡터 / C2 하이브리드(RRF) / C3 trigram + LLM 후보 선택 / C4 하이브리드 + LLM 후보 선택.
  C1·C2·C4는 임베딩이 적재되어 있어야 합니다(scripts/build_embeddings.py). 계획서 6절의 'C3 = C2 + LLM'은 여기서 C4입니다.
--split test 는 최종 측정용입니다. 결과를 본 뒤 평가셋·설정을 고치면 이력에 기록하십시오(평가 계획서 3.2절).
실행 중 LLM 호출 한도를 위해 DAILY_LLM_LIMIT을 이 실행에서만 크게 올립니다. 키 값은 기록하지 않습니다.
"""
import argparse
import json
import math
import random
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from load_to_db import read_env  # noqa: E402

CONFIGS = {  # 이름: (검색 방식, LLM 사용)
    "C0": ("trigram", False), "C1": ("vector", False), "C2": ("hybrid", False),
    "C3": ("trigram", True), "C4": ("hybrid", True),
}

DS = ROOT / "eval" / "datasets"
KST = timezone(timedelta(hours=9))
BOOT = 1000


def load_env_into_settings():
    from app.core import config
    env = read_env(ROOT / "backend" / ".env")
    s = config.settings
    for k in ("database_url", "gemini_api_key", "groq_api_key", "gemini_model", "groq_model", "embedding_model"):
        v = env.get(k.upper())
        if v:
            setattr(s, k, v)
    s.daily_llm_limit = 100000
    s.rate_limit_per_minute = 100000
    return s


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def key_of(code, c):
    return f"{code}|{c['name']}|{c['spec']}"


def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def boot_ci(per_case, seed=20261116):
    """per_case: 문항별 (합, 개수) 목록. 문항 단위 재표집 → 가중 평균의 95% 구간."""
    if not per_case:
        return None
    rng = random.Random(seed)
    n = len(per_case)
    vals = []
    for _ in range(BOOT):
        s = c = 0
        for _ in range(n):
            a, b = per_case[rng.randrange(n)]
            s += a
            c += b
        if c:
            vals.append(s / c)
    vals.sort()
    tot = sum(a for a, _ in per_case)
    cnt = sum(b for _, b in per_case)
    ci = [round(pct(vals, 0.025), 4), round(pct(vals, 0.975), 4)] if vals else [None, None]  # 대상 줄이 0개면 구간 없음
    return {"value": round(tot / cnt, 4) if cnt else None, "ci95": ci,
            "n_lines": cnt, "n_cases": n}


def ndcg_at(ranked_grades, ideal_grades, k=5):
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ranked_grades[:k]))
    ideal = sorted(ideal_grades, reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


# ---------------- 매칭 ----------------
def run_matching(cases, config, sleep):
    from app.core.database import get_engine
    from app.services import usage
    from app.services.line_parser import parse_lines
    from app.services.llm import LlmUnavailable, set_llm_override
    from app.services.item_search import EMBED_FALLBACKS
    from app.services.matcher import FETCH_LIMIT, _search, match_lines

    if not CONFIGS[config][1]:
        def off(batch):
            raise LlmUnavailable(config + ": LLM 사용 안 함")
        set_llm_override(off)
    out = []
    with get_engine().connect() as conn:
        for c in cases:
            code = c["municipality_code"]
            usage.reset_for_tests()
            parsed = parse_lines(c["input"])
            fb0 = EMBED_FALLBACKS["count"]
            t0 = time.perf_counter()
            lines, degraded, reason = match_lines(conn, code, parsed)
            latency = int((time.perf_counter() - t0) * 1000)
            # L1: 검색만(상위 5)
            retrieval = [[key_of(code, r) for r in _search(conn, code, pl.query)[:FETCH_LIMIT]] if pl.query else [] for pl in parsed]
            out.append({"case": c, "lines": lines, "retrieval": retrieval, "degraded": degraded,
                        "degraded_reason": reason, "latency_ms": latency, "n_parsed": len(parsed),
                        "embedding_fallbacks": EMBED_FALLBACKS["count"] - fb0})
            if CONFIGS[config][1] and sleep and not degraded:
                time.sleep(sleep)
            if CONFIGS[config][0] != "trigram":
                time.sleep(0.7 * len(parsed))  # 무료 임베딩 한도(분당 100회) 보호: 질의 임베딩 호출을 분당 약 85회 이하로
    return out


def score_matching(results):
    l1 = {"recall@1": [], "recall@3": [], "recall@5": [], "mrr": [], "ndcg@5": [],
          "strict_recall@1": [], "strict_recall@3": [], "strict_recall@5": [], "strict_mrr": []}
    top1, qty, wrong_matched = [], [], []
    confusion = {}
    mismatch = 0
    detail = []
    for r in results:
        c = r["case"]
        code = c["municipality_code"]
        exp = c["expected"]
        if r["n_parsed"] != len(exp):
            mismatch += 1
        per = {"case_id": c["case_id"], "category": c["category"], "split": c["split"], "lines": []}
        sel = {"recall@1": [0, 0], "recall@3": [0, 0], "recall@5": [0, 0], "mrr": [0, 0], "ndcg@5": [0, 0],
               "strict_recall@1": [0, 0], "strict_recall@3": [0, 0], "strict_recall@5": [0, 0], "strict_mrr": [0, 0]}
        t1 = [0, 0]
        qq = [0, 0]
        wm = [0, 0]
        for i, e in enumerate(exp):
            gold = {g["gold_key"]: g["grade"] for g in e["gold"]}
            got = r["lines"][i] if i < len(r["lines"]) else None
            ranked = r["retrieval"][i] if i < len(r["retrieval"]) else []
            if gold:
                rel = [rank for rank, k in enumerate(ranked) if gold.get(k, 0) >= 1]
                for k in (1, 3, 5):
                    sel["recall@%d" % k][0] += 1 if rel and rel[0] < k else 0
                    sel["recall@%d" % k][1] += 1
                sel["mrr"][0] += (1.0 / (rel[0] + 1)) if rel else 0.0
                sel["mrr"][1] += 1
                if 2 in gold.values():  # 규격까지 특정된 줄: grade 2 정답만 인정(엄격)
                    rel2 = [rank for rank, k in enumerate(ranked) if gold.get(k, 0) == 2]
                    for k in (1, 3, 5):
                        sel["strict_recall@%d" % k][0] += 1 if rel2 and rel2[0] < k else 0
                        sel["strict_recall@%d" % k][1] += 1
                    sel["strict_mrr"][0] += (1.0 / (rel2[0] + 1)) if rel2 else 0.0
                    sel["strict_mrr"][1] += 1
                sel["ndcg@5"][0] += ndcg_at([gold.get(k, 0) for k in ranked], list(gold.values()), 5)
                sel["ndcg@5"][1] += 1
            actual_status = got["status"] if got else "missing"
            confusion.setdefault(e["status"], {}).setdefault(actual_status, 0)
            confusion[e["status"]][actual_status] += 1
            sel_key = None
            if got and got["selected_item_id"] is not None:
                for cand in got["candidates"]:
                    if cand["item_id"] == got["selected_item_id"]:
                        sel_key = key_of(code, cand)
            if e["status"] == "matched":
                t1[1] += 1
                t1[0] += 1 if sel_key and gold.get(sel_key) == 2 else 0
            if got and got["status"] == "matched":
                wm[1] += 1
                wm[0] += 1 if (not gold or gold.get(sel_key, 0) == 0) else 0
            qq[1] += 1
            qq[0] += 1 if got and got["quantity"] == e["quantity"] else 0
            per["lines"].append({"expected_status": e["status"], "actual_status": actual_status, "selected": sel_key,
                                 "top3": [key_of(code, x).split("|", 1)[1] for x in (got["candidates"] if got else [])],
                                 "quantity": [e["quantity"], got["quantity"] if got else None]})
        for k, v in sel.items():
            l1[k].append(tuple(v))
        top1.append(tuple(t1))
        qty.append(tuple(qq))
        wrong_matched.append(tuple(wm))
        per["degraded"] = r["degraded"]
        per["latency_ms"] = r["latency_ms"]
        detail.append(per)
    lat = sorted(r["latency_ms"] for r in results)
    metrics = {"L1_" + k: boot_ci(v) for k, v in l1.items()}
    metrics["L2_top1_accuracy(expected matched lines)"] = boot_ci(top1)
    metrics["L2_quantity_accuracy"] = boot_ci(qty)
    metrics["L2_wrong_matched_rate(of matched outputs)"] = boot_ci(wrong_matched)
    metrics["L2_status_confusion(expected->actual)"] = confusion
    metrics["line_count_mismatch_cases"] = mismatch
    metrics["degraded_cases"] = sum(1 for r in results if r["degraded"])
    metrics["latency_ms"] = {"p50": pct(lat, 0.5), "p95": pct(lat, 0.95)}
    by_cat = {}
    for d in detail:
        by_cat.setdefault(d["category"], []).append(d)
    cat_stats = {}
    for cat, ds in by_cat.items():
        lines = [ln for d in ds for ln in d["lines"]]
        ok_status = sum(1 for ln in lines if ln["expected_status"] == ln["actual_status"])
        ok_qty = sum(1 for ln in lines if ln["quantity"][0] == ln["quantity"][1])
        cat_stats[cat] = {"lines": len(lines), "status_match": round(ok_status / len(lines), 3), "quantity_match": round(ok_qty / len(lines), 3)}
    metrics["by_category"] = cat_stats
    return metrics, detail


# ---------------- 절차 질문 ----------------
def run_procedure(cases, sleep):
    from app.core.database import get_engine
    from app.services import usage
    from app.services.llm import LlmUnavailable
    from app.services.procedure import REFUSE, UNSUPPORTED_ANSWER, answer_question, fetch_chunks
    from sqlalchemy import text

    out = []
    with get_engine().connect() as conn:
        for c in cases:
            code = c["municipality_code"]
            usage.reset_for_tests()
            sup = conn.execute(text("SELECT procedure_supported FROM municipalities WHERE code=:c"), {"c": code}).scalar()
            t0 = time.perf_counter()
            err = None
            try:
                if not sup:
                    res = {"answerable": False, "answer": UNSUPPORTED_ANSWER, "citations": []}
                else:
                    chunks = fetch_chunks(conn, code)
                    res = answer_question(chunks, c["question"])
                    full = {ch["id"]: ch["content"] for ch in chunks}  # 충실도 판정에는 잘리지 않은 근거 전문을 쓴다
            except LlmUnavailable as e:
                res, err = {"answerable": None, "answer": "", "citations": []}, str(e)
            out.append({"case": c, "res": res, "error": err, "latency_ms": int((time.perf_counter() - t0) * 1000),
                        "evidence_full": [full[x["chunk_id"]] for x in res["citations"] if x["chunk_id"] in full] if sup else []})
            if sleep:
                time.sleep(sleep)
    return out


def add_faithfulness(results, k, sleep):
    """답변이 나온 '답변 가능' 문항에 충실도 판정(K회 다수결)을 붙인다."""
    from app.services.judge import judge_faithfulness
    for r in results:
        res = r["res"]
        if r["case"]["kind"] == "answerable" and not r["error"] and res["answerable"] is True:
            r["faith"] = judge_faithfulness(res["answer"], r["evidence_full"] or [x["excerpt"] for x in res["citations"]], k)
            if sleep:
                time.sleep(sleep)


def score_procedure(results):
    from app.services.procedure import REFUSE, UNSUPPORTED_ANSWER
    ans_cases = [r for r in results if r["case"]["kind"] == "answerable"]
    un_cases = [r for r in results if r["case"]["kind"] == "unanswerable"]
    unsup = [r for r in results if r["case"]["kind"] == "unsupported"]
    errs = [r for r in results if r["error"]]
    detail = []
    cit_ok, src_hit, facts_ok, over_ref, faith = [], [], [], [], []
    for r in ans_cases:
        if r["error"]:
            continue
        res, c = r["res"], r["case"]
        answered = res["answerable"] is True
        over_ref.append((0 if answered else 1, 1))
        secs = {x["section"] for x in res["citations"]}
        cit_ok.append((1 if answered and res["citations"] else 0, 1))
        src_hit.append((1 if answered and all(g in secs for g in c["gold_sources"]) else 0, 1))
        blob = res["answer"] + " " + " ".join(x["excerpt"] for x in res["citations"])
        facts_ok.append((1 if answered and all(f in blob for f in c["must_include"]) else 0, 1))
        f = r.get("faith")
        if f and f["supported"] is not None:
            faith.append((1 if f["supported"] else 0, 1))
        detail.append({"case_id": c["case_id"], "kind": c["kind"], "answerable": res["answerable"], "answer": res["answer"],
                       "cited_sections": sorted(secs), "faithfulness": f})
    refuse_ok = []
    for r in un_cases:
        if r["error"]:
            continue
        res = r["res"]
        refuse_ok.append((1 if res["answerable"] is False and not res["citations"] else 0, 1))
        detail.append({"case_id": r["case"]["case_id"], "kind": "unanswerable", "answerable": res["answerable"], "answer": res["answer"]})
    unsup_ok = []
    for r in unsup:
        res = r["res"]
        unsup_ok.append((1 if res["answerable"] is False and res["answer"] == UNSUPPORTED_ANSWER else 0, 1))
        detail.append({"case_id": r["case"]["case_id"], "kind": "unsupported", "answerable": res["answerable"], "answer": res["answer"]})
    lat = sorted(r["latency_ms"] for r in results)
    m = {"L3_over_refusal_rate(answerable→refused)": boot_ci(over_ref),
         "L3_citation_present_rate": boot_ci(cit_ok),
         "L3_gold_source_hit_rate": boot_ci(src_hit),
         "L3_must_include_rate": boot_ci(facts_ok),
         "L3_refusal_accuracy(unanswerable)": boot_ci(refuse_ok),
         "L3_unsupported_accuracy": boot_ci(unsup_ok),
         "llm_unavailable_cases": len(errs), "latency_ms": {"p50": pct(lat, 0.5), "p95": pct(lat, 0.95)},
         "note": "충실도는 --judge K 로 측정(미지정 시 미실시)"}
    if faith:
        m["L3_faithfulness_rate(judge majority)"] = boot_ci(faith)
        m["L3_judge_unjudged_cases"] = sum(1 for r in results if r.get("faith") and r["faith"]["supported"] is None)
        m["L3_judge_unanimous_rate"] = round(sum(1 for r in results if r.get("faith") and r["faith"]["unanimous"]) /
                                             max(1, sum(1 for r in results if r.get("faith") and r["faith"]["supported"] is not None)), 4)
    return m, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=list(CONFIGS), default="C3")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--layer", choices=["matching", "procedure", "all"], default="all")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=0.0, help="LLM 사용 구성에서 문항 사이 대기(초). 무료 분당 한도 보호")
    ap.add_argument("--judge", type=int, default=0, help="충실도 판정 횟수 K(0이면 안 함, 보통 3). LLM 호출이 문항당 K회 늘어납니다")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.split in ("test", "all"):
        print("주의: 검증용(test) 문항은 최종 측정 1회에만 사용하십시오. 5초 안에 취소할 수 있습니다.")
        time.sleep(5)
    s = load_env_into_settings()
    if not s.database_url:
        print("backend/.env 에 DATABASE_URL이 없습니다.")
        return 1
    retrieval, uses_llm = CONFIGS[a.config]
    if uses_llm and not (s.gemini_api_key or s.groq_api_key):
        print(a.config + "는 LLM 키가 필요합니다(backend/.env).")
        return 1
    if retrieval != "trigram":
        if not s.gemini_api_key:
            print(a.config + "는 질의 임베딩에 GEMINI_API_KEY가 필요합니다(backend/.env).")
            return 1
        from sqlalchemy import text as _t
        from app.core.database import get_engine
        with get_engine().connect() as c:
            n = c.execute(_t("SELECT count(*) FROM item_catalog WHERE embedding IS NOT NULL")).scalar()
        if not n:
            print("item_catalog에 임베딩이 없습니다. 먼저 scripts/build_embeddings.py를 실행하십시오.")
            return 1
    s.retrieval_mode = retrieval

    from app.services.llm import set_procedure_override  # noqa: F401
    pick = lambda rows: [r for r in rows if a.split == "all" or r["split"] == a.split]
    matching = pick(load_jsonl(DS / "v1" / "matching.jsonl")) if a.layer in ("matching", "all") else []
    procedure = pick(load_jsonl(DS / "v1" / "procedure.jsonl")) if a.layer in ("procedure", "all") and uses_llm else []

    stamp = datetime.now(KST).strftime("%Y%m%dT%H%M")
    runs = []
    for rep in range(a.repeat):
        rec = {"repeat_index": rep}
        if matching:
            res = run_matching(matching, a.config, a.sleep)
            rec["matching_metrics"], rec["matching_cases"] = score_matching(res)
            rec["embedding_fallback_queries"] = sum(r.get("embedding_fallbacks", 0) for r in res)
            if rec["embedding_fallback_queries"]:
                print(f"경고: 질의 임베딩 실패로 trigram으로 대신한 검색이 {rec['embedding_fallback_queries']}건입니다. "
                      "이 실행의 벡터·하이브리드 결과는 순수한 값이 아니므로 한도가 풀린 뒤 다시 실행하십시오.")
        if procedure:
            res = run_procedure(procedure, a.sleep)
            if a.judge:
                add_faithfulness(res, a.judge, a.sleep)
            rec["procedure_metrics"], rec["procedure_cases"] = score_procedure(res)
        runs.append(rec)
        print(f"반복 {rep + 1}/{a.repeat} 완료")

    out = {"run_id": f"{stamp}_{a.config}_{a.split}", "git_commit": git_commit(), "dataset_version": "v1", "split": a.split,
           "models": {"llm_primary": s.gemini_model if uses_llm else None,
                      "llm_fallback": s.groq_model if uses_llm else None, "embedding": s.embedding_model if retrieval != "trigram" else None, "judge": (s.gemini_model + " / " + s.groq_model + " (K=%d)" % a.judge) if a.judge else None},
           "config": {"name": a.config, "retrieval": retrieval, "top_k": 5}, "repeat": a.repeat, "runs": runs, "notes": a.note}
    d = ROOT / "eval" / "runs"
    d.mkdir(exist_ok=True)
    path = d / f"{out['run_id']}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("저장:", path.relative_to(ROOT))
    for rec in runs[:1]:
        for name in ("matching_metrics", "procedure_metrics"):
            for k, v in rec.get(name, {}).items():
                if isinstance(v, dict) and "value" in v:
                    print(f"  {k}: {v['value']} (95% CI {v['ci95'][0]}~{v['ci95'][1]}, 줄 {v['n_lines']})")
                elif k in ("L2_status_confusion(expected->actual)", "by_category", "latency_ms"):
                    print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
