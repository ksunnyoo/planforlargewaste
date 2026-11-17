/** 평가 결과(2026-11-17 기준). 수치는 eval/runs/*.json 원본에서 옮겼고, run_id로 원본을 찾을 수 있다. */

export type Frac = [number, number]; // [분자, 분모]

export interface TestRow {
  config: string;
  name: string;
  recall1: string;
  exact: Frac;
  wrong: Frac;
  ambToMatched: Frac;
  unmatchedOk: Frac;
  latency: string;
  runId: string;
  note?: string;
}

export const TEST_ROWS: TestRow[] = [
  { config: "C0", name: "trigram", recall1: "0.82 (0.63~1.0)", exact: [1, 6], wrong: [0, 1], ambToMatched: [0, 11], unmatchedOk: [1, 2], latency: "0.22초 / 0.92초", runId: "20261117T0728_C0_test" },
  { config: "C2", name: "하이브리드", recall1: "1.0 (1.0~1.0)", exact: [1, 6], wrong: [0, 1], ambToMatched: [0, 11], unmatchedOk: [0, 2], latency: "0.90초 / 1.0초", runId: "20261117T0730_C2_test", note: "임베딩 실패 0건" },
  { config: "C3", name: "trigram + LLM 선택", recall1: "0.82 (0.63~1.0)", exact: [6, 6], wrong: [0, 8], ambToMatched: [2, 11], unmatchedOk: [1, 2], latency: "2.2초 / 7.6초", runId: "20261117T0749_C3_test", note: "3회 반복 결과 동일" },
];

export interface DevRow {
  config: string;
  name: string;
  exact: Frac;
  wrong: Frac | null;
  ambToMatched: Frac;
  runId: string;
  note?: string;
}

export const DEV_ROWS: DevRow[] = [
  { config: "C0", name: "trigram", exact: [12, 16], wrong: [0, 13], ambToMatched: [1, 25], runId: "20261116T1234_C0_dev" },
  { config: "C1", name: "벡터", exact: [0, 16], wrong: null, ambToMatched: [0, 25], runId: "20261116T1729_C1_dev", note: "벡터 단독 후보는 점수를 0.7로 제한해 자동 확정 기준(0.9)에 닿지 않음. 검색 능력이 0이라는 뜻이 아님" },
  { config: "C2", name: "하이브리드", exact: [8, 16], wrong: [0, 8], ambToMatched: [0, 25], runId: "20261116T1726_C2_dev" },
  { config: "C3", name: "trigram + LLM 선택", exact: [16, 16], wrong: [0, 16], ambToMatched: [0, 25], runId: "20261116T1338_C3_dev" },
  { config: "C4", name: "하이브리드 + LLM 선택", exact: [16, 16], wrong: [0, 16], ambToMatched: [0, 25], runId: "20261116T1731_C4_dev", note: "검증용 측정은 하지 않음(미실시)" },
];

export const PROCEDURE_TEST: { label: string; value: string }[] = [
  { label: "답변 가능한 질문에 답함(과거절 없음)", value: "3/3" },
  { label: "인용 포함", value: "3/3" },
  { label: "근거 출처 적중", value: "3/3" },
  { label: "필수 단어 포함", value: "3/3" },
  { label: "충실도(판정 모델 3회 투표)", value: "3/3" },
  { label: "답변 불가 질문을 거절", value: "1/1" },
  { label: "수수료만 제공하는 지자체 처리", value: "1/1" },
];

export const GLOSSARY: { term: string; text: string }[] = [
  { term: "trigram", text: "글자 3개 단위가 겹치는 정도로 비슷한 품목을 찾는 방식입니다." },
  { term: "벡터", text: "뜻이 가까운 말을 숫자로 바꿔 비교하는 방식입니다." },
  { term: "하이브리드(RRF)", text: "trigram과 벡터의 순위를 합쳐 최종 순위를 정하는 방식입니다." },
  { term: "LLM 선택", text: "후보 목록 안에서만 언어 모델이 하나를 고르게 하는 방식입니다. 금액 계산에는 쓰지 않습니다." },
  { term: "recall@1", text: "정답이 1순위로 나온 비율입니다." },
  { term: "정확 확정", text: "확정해야 하는 줄에서 정답을 골라 확정한 수입니다." },
  { term: "확정 오답", text: "확정으로 처리한 줄 중 정답이 아닌 수입니다." },
  { term: "되물어야 하는데 확정", text: "여러 후보가 정답이라 사용자에게 물어야 하는 줄을 자동 확정한 수입니다. 낮을수록 좋습니다." },
  { term: "95% 구간", text: "문항을 다시 뽑아 1,000번 계산한 범위입니다. 줄 수가 적으면 넓어집니다." },
];

export const LIMITS: string[] = [
  "검증용 매칭은 19줄(확정해야 할 줄 6, 되물어야 할 줄 11, 미매칭 2)이고 평가셋 작성자는 1인입니다. 줄 수가 적어 구간이 넓습니다.",
  "C3의 6/6은 6줄 중 6줄이라는 뜻이며, 항상 맞는다는 근거가 되지 못합니다.",
  "C3는 되물어야 하는 11줄 중 2줄을 자동 확정했습니다. 정답으로 인정되는 후보 중 하나를 골랐지만 사용자에게 물어야 하는 줄입니다.",
  "C0와 C2의 recall@1 차이는 구간이 겹쳐 우열을 말할 수 없습니다.",
  "개발용 수치는 프롬프트와 확정 기준을 조정하는 데 쓰였으므로 성능 추정이 아닙니다.",
  "C4는 개발용만 측정했고 검증용 측정은 하지 않았습니다(미실시).",
  "절차 질의는 검증용 5건(답변 가능 3, 답변 불가 1, 미지원 1)이라 일반화하지 않습니다.",
];

export const REPO = "https://github.com/ksunnyoo/planforlargewaste";
export const LINKS: { label: string; href: string }[] = [
  { label: "평가 실행 원본(eval/runs)", href: REPO + "/tree/main/eval/runs" },
  { label: "평가 일지(eval_log.md)", href: REPO + "/blob/main/docs/research/eval_log.md" },
  { label: "최종 보고서", href: REPO + "/blob/main/docs/report/FINAL_REPORT.md" },
  { label: "평가 계획서", href: REPO + "/blob/main/docs/06_EVAL_PLAN.md" },
];
