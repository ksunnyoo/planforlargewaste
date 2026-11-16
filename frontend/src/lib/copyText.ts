import type { Estimate } from "../api/types";
import { dateKo, DISCLAIMER, feeLabel, SPEC_MISSING, won } from "./format";

/** 견적 내용을 메신저·문서에 붙여넣기 좋은 글로 만든다(화면 표시와 같은 값만 사용). */
export function estimateToText(e: Estimate, municipalityName: string): string {
  const out: string[] = [];
  out.push(`[대형폐기물 배출 견적] ${municipalityName}`);
  out.push("");
  out.push("■ 품목별 수수료");
  for (const l of e.lines) {
    const spec = l.item.spec === SPEC_MISSING ? "규격 미기재" : l.item.spec;
    const fee = l.fee_type === "paid" ? won(l.municipal_fee_won) : feeLabel(l.fee_type, l.unit_fee_won);
    const work = l.operator_fee_won > 0 ? ` / 업체 작업비 ${won(l.operator_fee_won)}` : "";
    out.push(`- ${l.item.name} (${spec}) ${l.quantity}개: ${fee}${work}`);
  }
  out.push(`지자체 수수료 합계: ${won(e.totals.municipal_fee_total_won)}`);
  if (e.totals.operator_fee_total_won > 0) {
    out.push(`업체 작업비 합계: ${won(e.totals.operator_fee_total_won)}`);
    out.push(`총액: ${won(e.totals.grand_total_won)}`);
  }
  const p = e.procedure;
  if (p.status === "ok") {
    out.push("", "■ 배출 절차");
    p.steps.forEach((s) => out.push(`${s.order}. ${s.title}: ${s.detail}`));
    if (p.checklist.length) {
      out.push("", "■ 확인 사항");
      p.checklist.forEach((c) => out.push(`- ${c.text}`));
    }
  } else if (p.warnings.length) {
    out.push("", "■ 배출 절차", ...p.warnings);
  }
  if (e.citations.length) {
    out.push("", "■ 근거");
    e.citations.forEach((c) =>
      out.push(`- ${c.source_name} · ${c.section} · ${c.base_date ? `기준일 ${dateKo(c.base_date)}` : "기준일 미확인"}`));
  }
  out.push("", `수수료 데이터 확인일: ${dateKo(e.data_base_date)} (견적 시점 기준 단가)`, DISCLAIMER);
  return out.join("\n");
}
