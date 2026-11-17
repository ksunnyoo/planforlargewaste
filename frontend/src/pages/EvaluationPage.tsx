import { Link } from "react-router-dom";
import { DEV_ROWS, GLOSSARY, LIMITS, LINKS, PROCEDURE_TEST, TEST_ROWS } from "../data/evalResults";
import type { Frac } from "../data/evalResults";
import { Badge, Banner, Card } from "../components/ui";

const frac = (f: Frac | null) => (f ? `${f[0]}/${f[1]}` : "확정 0건");

function Bar({ label, value, tone = "brand" }: { label: string; value: Frac; tone?: "brand" | "warn" }) {
  const pct = value[1] === 0 ? 0 : Math.round((value[0] / value[1]) * 100);
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-14 shrink-0 font-medium">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${label} ${frac(value)}`}>
        <div className={`h-full rounded-full ${tone === "warn" ? "bg-warn" : "bg-brand"}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 shrink-0 text-right tabular-nums">{frac(value)}</span>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="whitespace-nowrap border-b border-line px-2 py-2 text-left text-xs font-semibold text-muted">{children}</th>;
}
function Td({ children, strong }: { children: React.ReactNode; strong?: boolean }) {
  return <td className={`border-b border-line/70 px-2 py-2 align-top ${strong ? "font-semibold" : ""}`}>{children}</td>;
}

export default function EvaluationPage() {
  return (
    <div className="space-y-4">
      <div>
        <Link to="/" className="text-sm font-semibold text-brand-dark underline">← 견적 계산으로 돌아가기</Link>
        <h1 className="mt-2 text-2xl font-bold">평가 결과</h1>
        <p className="mt-1 text-sm text-muted">품목 매칭과 절차 안내를 직접 만든 평가셋으로 측정한 결과입니다. 2026-11-17 기준입니다.</p>
      </div>

      <Banner tone="info" title="검증용 문항은 구성마다 1회만 사용했습니다.">
        시스템을 동결한 뒤 측정했고, 결과를 본 뒤 코드와 평가셋을 바꾸지 않았습니다. 평가셋은 매칭 64문항, 절차 16문항입니다.
      </Banner>

      <Card>
        <h2 className="text-lg font-bold">검증용 최종 측정</h2>
        <p className="mt-1 text-xs text-muted">매칭 19줄: 확정해야 할 줄 6, 되물어야 할 줄 11, 미매칭 2. 검색 지표(recall@1)는 정답이 있는 17줄로 계산했습니다.</p>

        <div className="mt-4 space-y-5">
          <div>
            <p className="mb-2 text-sm font-semibold">확정해야 할 6줄을 맞게 확정한 수 (높을수록 좋음)</p>
            <div className="space-y-2">
              {TEST_ROWS.map((r) => <Bar key={r.config} label={r.config} value={r.exact} />)}
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm font-semibold">되물어야 하는 11줄을 자동 확정한 수 (낮을수록 좋음)</p>
            <div className="space-y-2">
              {TEST_ROWS.map((r) => <Bar key={r.config} label={r.config} value={r.ambToMatched} tone="warn" />)}
            </div>
          </div>
        </div>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-sm">
            <thead>
              <tr><Th>구성</Th><Th>recall@1 (95% 구간)</Th><Th>정확 확정</Th><Th>확정 오답</Th><Th>미매칭 정확</Th><Th>지연 p50 / p95</Th></tr>
            </thead>
            <tbody>
              {TEST_ROWS.map((r) => (
                <tr key={r.config}>
                  <Td strong>{r.config}<span className="block text-xs font-normal text-muted">{r.name}</span></Td>
                  <Td>{r.recall1}</Td>
                  <Td>{frac(r.exact)}</Td>
                  <Td>{frac(r.wrong)}</Td>
                  <Td>{frac(r.unmatchedOk)}</Td>
                  <Td>{r.latency}{r.note && <span className="block text-xs text-muted">{r.note}</span>}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">원본: {TEST_ROWS.map((r) => r.runId).join(", ")}</p>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">절차 안내(C3, 검증용 5건)</h2>
        <ul className="mt-3 divide-y divide-line text-sm">
          {PROCEDURE_TEST.map((p) => (
            <li key={p.label} className="flex items-center justify-between gap-3 py-2">
              <span>{p.label}</span>
              <Badge tone="ok">{p.value}</Badge>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted">표본이 5건이라 일반화하지 않습니다.</p>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">해석</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm">
          <li>LLM이 후보 중에서 고르게 하면 확정해야 할 6줄을 모두 확정했습니다(3회 반복 모두 같음). 검색 방식만 바꾼 C0, C2는 1줄입니다.</li>
          <li>확정 출력 중 오답은 모든 구성에서 0건입니다.</li>
          <li>다만 C3는 되물어야 하는 11줄 중 2줄을 자동 확정했습니다. 개발용에서는 0/25였으므로 개발용 조정이 검증용으로 완전히 일반화되지는 않았습니다.</li>
          <li>C2는 recall@1이 높아지는 방향이지만 구간이 겹쳐 하이브리드가 낫다고 결론 내리지 않습니다.</li>
        </ul>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">개발용 측정 (참고, 성능 추정 아님)</h2>
        <Banner tone="warn">프롬프트와 확정 기준을 조정하는 데 쓴 문항의 값입니다. 검색 recall@1은 모든 구성에서 1.0이어서 검색 방식 간 차이를 구별하지 못했습니다.</Banner>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[30rem] border-collapse text-sm">
            <thead>
              <tr><Th>구성</Th><Th>정확 확정(16줄)</Th><Th>확정 오답</Th><Th>되물어야 하는데 확정(25줄)</Th></tr>
            </thead>
            <tbody>
              {DEV_ROWS.map((r) => (
                <tr key={r.config}>
                  <Td strong>{r.config}<span className="block text-xs font-normal text-muted">{r.name}</span></Td>
                  <Td>{frac(r.exact)}</Td>
                  <Td>{frac(r.wrong)}</Td>
                  <Td>{frac(r.ambToMatched)}{r.note && <span className="block text-xs text-muted">{r.note}</span>}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">C1, C2, C4는 질의 임베딩 실패 0건을 확인한 재측정(2026-11-16 17시 이후)이며, 그 전의 임베딩 실행은 무효로 정정했습니다. 원본: {DEV_ROWS.map((r) => r.runId).join(", ")}</p>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">한계</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm">
          {LIMITS.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">용어</h2>
        <dl className="mt-2 space-y-2 text-sm">
          {GLOSSARY.map((g) => (
            <div key={g.term}>
              <dt className="font-semibold">{g.term}</dt>
              <dd className="text-muted">{g.text}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card>
        <h2 className="text-lg font-bold">원본과 기록</h2>
        <ul className="mt-2 space-y-1 text-sm">
          {LINKS.map((l) => (
            <li key={l.href}>
              <a href={l.href} target="_blank" rel="noreferrer" className="text-brand-dark underline">{l.label}</a>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
