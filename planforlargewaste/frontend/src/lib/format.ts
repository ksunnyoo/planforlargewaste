import type { FeeType } from "../api/types";

const nf = new Intl.NumberFormat("ko-KR");
export const won = (n: number) => `${nf.format(n)}원`;

/** 수수료 유형에 맞는 표시 문구: 유료는 금액, 무료·면제는 문구. */
export function feeLabel(feeType: FeeType, amount: number): string {
  if (feeType === "free") return "무료";
  if (feeType === "exempt") return "면제";
  return won(amount);
}

export function dateKo(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
}

export const SPEC_MISSING = "규격 미기재";
export const DISCLAIMER = "실제 수수료와 절차는 해당 지자체의 안내를 확인하십시오.";
