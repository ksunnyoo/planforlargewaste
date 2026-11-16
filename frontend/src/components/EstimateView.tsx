import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMunicipalities } from "../api/hooks";
import type { Estimate } from "../api/types";
import { estimateToText } from "../lib/copyText";
import { dateKo, DISCLAIMER, feeLabel, SPEC_MISSING, won } from "../lib/format";
import { useDraftStore } from "../store/draftStore";
import FeedbackCard from "./FeedbackCard";
import { MunicipalityNotices, SupportBadge } from "./MunicipalityPicker";
import { Badge, Banner, Button, Card, Icon } from "./ui";

function shareUrl(publicId: string) {
  return `${window.location.origin}${import.meta.env.BASE_URL}#/s/${publicId}`;
}

function ProcedurePanel({ e }: { e: Estimate }) {
  const p = e.procedure;
  return (
    <Card>
      <h2 className="text-sm font-bold">배출 절차</h2>
      {p.status === "ok" && (
        <>
          <ol className="mt-3 space-y-3">
            {p.steps.map((s) => (
              <li key={s.order} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-white">{s.order}</span>
                <div>
                  <p className="text-sm font-semibold">{s.title}</p>
                  <p className="text-sm text-slate-700">{s.detail}</p>
                </div>
              </li>
            ))}
          </ol>
          {p.checklist.length > 0 && (
            <ul className="mt-4 space-y-1.5 rounded-xl bg-brand-soft p-3 text-sm">
              {p.checklist.map((c, i) => (
                <li key={i} className="flex gap-2">
                  <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                  {c.text}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {p.status !== "ok" && (
        <div className="mt-3 space-y-2">
          {p.warnings.map((w, i) => (
            <Banner key={i} tone={p.status === "raw_chunks" ? "warn" : "info"}>{w}</Banner>
          ))}
        </div>
      )}
      {p.status === "raw_chunks" && (
        <ul className="mt-3 space-y-2">
          {e.citations.map((c) => (
            <li key={c.chunk_id} className="rounded-xl border border-line p-3 text-sm">
              <p className="font-semibold">{c.section}</p>
              <p className="mt-1 whitespace-pre-line text-slate-700">{c.excerpt}</p>
            </li>
          ))}
        </ul>
      )}
      {e.citations.length > 0 && (
        <div className="mt-4 border-t border-line pt-3 text-xs text-muted">
          <p className="font-semibold">근거</p>
          <ul className="mt-1 space-y-1">
            {e.citations.map((c) => (
              <li key={c.chunk_id}>
                {c.source_name} · {c.section} · {c.base_date ? `기준일 ${dateKo(c.base_date)}` : "기준일 미확인"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export default function EstimateView({ estimate: e, readOnly }: { estimate: Estimate; readOnly: boolean }) {
  const navigate = useNavigate();
  const reset = useDraftStore((s) => s.reset);
  const { data: munis } = useMunicipalities();
  const muni = munis?.find((m) => m.code === e.municipality_code);
  const [copied, setCopied] = useState(false);
  const t = e.totals;
  const hasOperator = t.operator_fee_total_won > 0;

  const [copiedText, setCopiedText] = useState(false);

  async function copyLink() {
    const url = shareUrl(e.public_id);
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("아래 주소를 복사하십시오.", url);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  async function copyContent() {
    const body = estimateToText(e, muni?.name ?? e.municipality_code);
    try {
      await navigator.clipboard.writeText(body);
    } catch {
      window.prompt("아래 내용을 복사하십시오.", body);
    }
    setCopiedText(true);
    setTimeout(() => setCopiedText(false), 2500);
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-muted">{readOnly ? "공유된 견적" : "견적 결과"}</p>
            <h1 className="mt-0.5 text-xl font-bold">{muni?.name ?? e.municipality_code}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              {muni && <SupportBadge m={muni} />}
              <span className="text-xs text-muted">
                {muni?.legal_effective_date ? "데이터 확인일" : "수수료 기준일"} {dateKo(e.data_base_date)}
                {muni?.legal_effective_date && ` · 조례 시행일 ${dateKo(muni.legal_effective_date)}`}
              </span>
            </div>
          </div>
          <div className="no-print flex flex-wrap gap-2">
            <Button variant="secondary" onClick={copyLink}>
              <Icon name={copied ? "check" : "link"} /> {copied ? "복사되었습니다" : "링크 복사"}
            </Button>
            <Button variant="secondary" onClick={copyContent}>
              <Icon name={copiedText ? "check" : "link"} /> {copiedText ? "복사되었습니다" : "내용 복사"}
            </Button>
            <Button variant="secondary" onClick={() => window.print()}>
              <Icon name="print" /> 인쇄
            </Button>
          </div>
        </div>
        {muni && <div className="mt-3"><MunicipalityNotices m={muni} /></div>}
      </Card>

      <Card>
        <h2 className="text-sm font-bold">품목별 수수료</h2>
        <ul className="mt-3 divide-y divide-line/70 sm:hidden">
          {e.lines.map((l) => (
            <li key={l.line_no} className="py-3 text-sm">
              <p className="font-semibold">{l.item.name}</p>
              <p className="text-xs text-muted">{l.item.spec === SPEC_MISSING ? "규격 미기재" : l.item.spec}</p>
              {l.fee_type === "exempt" && (
                <p className="mt-1 text-xs text-info">무상 방문 수거 대상일 수 있습니다. 문의 1599-0903</p>
              )}
              <dl className="mt-2 grid grid-cols-2 gap-y-1 text-xs">
                <dt className="text-muted">수량</dt>
                <dd className="text-right tabular-nums">{l.quantity}</dd>
                <dt className="text-muted">단가</dt>
                <dd className="text-right tabular-nums">{l.fee_type === "paid" ? won(l.unit_fee_won) : feeLabel(l.fee_type, 0)}</dd>
                <dt className="font-semibold">지자체 수수료</dt>
                <dd className="text-right text-sm font-bold tabular-nums">{l.fee_type === "paid" ? won(l.municipal_fee_won) : feeLabel(l.fee_type, 0)}</dd>
                {l.operator_fee_won > 0 && (
                  <>
                    <dt className="text-muted">업체 작업비</dt>
                    <dd className="text-right tabular-nums">{won(l.operator_fee_won)}</dd>
                  </>
                )}
              </dl>
            </li>
          ))}
        </ul>
        <div className="mt-3 hidden overflow-x-auto sm:block">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 pr-2 font-semibold">품목 · 규격</th>
                <th className="px-2 text-right font-semibold">수량</th>
                <th className="px-2 text-right font-semibold">단가</th>
                <th className="px-2 text-right font-semibold">지자체 수수료</th>
                <th className="pl-2 text-right font-semibold">업체 작업비</th>
              </tr>
            </thead>
            <tbody>
              {e.lines.map((l) => (
                <tr key={l.line_no} className="border-b border-line/70 align-top">
                  <td className="py-2.5 pr-2">
                    <p className="font-semibold">{l.item.name}</p>
                    <p className="text-xs text-muted">{l.item.spec === SPEC_MISSING ? "규격 미기재" : l.item.spec}</p>
                    {l.fee_type === "exempt" && (
                      <p className="mt-1 text-xs text-info">무상 방문 수거 대상일 수 있습니다. 문의 1599-0903</p>
                    )}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums">{l.quantity}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums">
                    {l.fee_type === "paid" ? won(l.unit_fee_won) : <Badge tone={l.fee_type === "free" ? "ok" : "info"}>{feeLabel(l.fee_type, 0)}</Badge>}
                  </td>
                  <td className="px-2 py-2.5 text-right font-semibold tabular-nums">
                    {l.fee_type === "paid" ? won(l.municipal_fee_won) : feeLabel(l.fee_type, 0)}
                  </td>
                  <td className="py-2.5 pl-2 text-right tabular-nums">{l.operator_fee_won > 0 ? won(l.operator_fee_won) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <dl className="mt-4 space-y-2 rounded-xl bg-canvas p-4 text-sm">
          <div className="flex justify-between gap-4">
            <dt>지자체 수수료 합계</dt>
            <dd className={`tabular-nums ${hasOperator ? "font-semibold" : "text-xl font-bold text-brand-dark"}`}>{won(t.municipal_fee_total_won)}</dd>
          </div>
          {hasOperator ? (
            <>
              <div className="flex justify-between gap-4">
                <dt>업체 작업비 합계</dt>
                <dd className="font-semibold tabular-nums">{won(t.operator_fee_total_won)}</dd>
              </div>
              <div className="flex justify-between gap-4 border-t border-line pt-2">
                <dt className="font-bold">총 예상 금액</dt>
                <dd className="text-xl font-bold tabular-nums text-brand-dark">{won(t.grand_total_won)}</dd>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted">업체 작업비는 입력되지 않았습니다. 작업비는 업체에 문의하십시오.</p>
          )}
        </dl>
        <p className="mt-2 text-xs text-muted">지자체 수수료와 업체 작업비는 구분하여 표시합니다. 금액은 견적을 만든 시점의 기준 단가입니다.</p>
      </Card>

      <ProcedurePanel e={e} />

      <FeedbackCard estimate={e} />

      <Card className="text-xs leading-relaxed text-muted">
        <p className="font-semibold text-slate-700">{DISCLAIMER}</p>
        <p className="mt-1">
          견적 생성일 {dateKo(e.created_at)} · 보관 만료일 {dateKo(e.expires_at)}
        </p>
      </Card>

      <div className="no-print">
        <Button
          variant="primary"
          className="w-full"
          onClick={() => {
            reset();
            navigate("/");
          }}
        >
          새 견적 만들기
        </Button>
      </div>
    </div>
  );
}
