import { useState } from "react";
import { useParseText } from "../api/hooks";
import type { ParseCandidate, ParseLine } from "../api/types";
import { feeLabel, SPEC_MISSING } from "../lib/format";
import { MAX_LINES, useDraftStore } from "../store/draftStore";
import { Badge, Banner, Button, Card, ErrorBox } from "./ui";

/** 문장 입력 → 줄별 후보 확인 → 담기. 서버는 후보만 제안하고, 담기는 사용자가 확정한다. */
export default function TextParse() {
  const code = useDraftStore((s) => s.municipalityCode);
  const addItem = useDraftStore((s) => s.addItem);
  const count = useDraftStore((s) => s.lines.length);
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Record<number, number | null>>({});
  const [done, setDone] = useState<Record<number, boolean>>({});
  const parse = useParseText();

  if (!code) return null;

  function analyze() {
    if (!code || !text.trim()) return;
    setDone({});
    parse.mutate(
      { municipality_code: code, text: text.trim() },
      {
        onSuccess: (res) => {
          const init: Record<number, number | null> = {};
          res.lines.forEach((l) => (init[l.line_no] = l.selected_item_id));
          setPicked(init);
        },
      },
    );
  }

  function add(line: ParseLine, cand: ParseCandidate) {
    addItem(cand, line.quantity);
    setDone((d) => ({ ...d, [line.line_no]: true }));
  }

  const res = parse.data;
  return (
    <Card>
      <label htmlFor="text-in" className="text-sm font-bold">
        여러 품목을 한 번에 입력하려면 문장으로 입력하십시오.
      </label>
      <p className="mt-1 text-xs text-muted">쉼표나 줄바꿈으로 구분하고 수량을 함께 적으십시오. 예: 3인용 소파, 책상, 의자 4개</p>
      <textarea
        id="text-in"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={500}
        rows={3}
        className="mt-2 w-full rounded-xl border border-line bg-white p-3 text-sm"
        placeholder="3인용 소파, 책상, 의자 4개"
      />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-muted">{text.length}/500</span>
        <Button onClick={analyze} disabled={!text.trim() || parse.isPending}>
          {parse.isPending ? "분석 중…" : "분석하기"}
        </Button>
      </div>
      {parse.isError && <ErrorBox message={parse.error.message} onRetry={analyze} />}

      {res && (
        <div className="mt-3 space-y-3" aria-live="polite">
          {res.degraded && (
            <Banner tone="warn" title="자동 선택을 사용할 수 없습니다.">
              검색 점수 기준 후보만 표시합니다. 알맞은 품목을 직접 선택하십시오.
            </Banner>
          )}
          {res.lines.map((l) => (
            <div key={l.line_no} className="rounded-xl border border-line p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold">
                  {l.raw_text} <span className="text-muted">· 수량 {l.quantity}개</span>
                </p>
                {done[l.line_no] ? (
                  <Badge tone="ok">담음</Badge>
                ) : l.status === "matched" ? (
                  <Badge tone="info">추천 선택됨</Badge>
                ) : l.status === "ambiguous" ? (
                  <Badge tone="warn">선택 필요</Badge>
                ) : (
                  <Badge tone="gray">후보 없음</Badge>
                )}
              </div>
              {l.note && <p className="mt-1 text-xs text-muted">{l.note}</p>}
              {l.candidates.length > 0 && (
                <fieldset className="mt-2 space-y-1">
                  <legend className="sr-only">{l.raw_text} 후보</legend>
                  {l.candidates.map((c) => (
                    <label key={c.item_id} className="flex cursor-pointer items-start gap-2 rounded-lg p-2 text-sm hover:bg-slate-50">
                      <input
                        type="radio"
                        name={`line-${l.line_no}`}
                        className="mt-1"
                        checked={picked[l.line_no] === c.item_id}
                        onChange={() => setPicked((p) => ({ ...p, [l.line_no]: c.item_id }))}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">{c.name}</span>{" "}
                        <span className="text-muted">{c.spec === SPEC_MISSING ? "규격 미기재" : c.spec}</span>
                        <span className="block text-xs text-muted">
                          {feeLabel(c.fee_type, c.fee_won)} · {c.reason}
                        </span>
                      </span>
                    </label>
                  ))}
                  <div className="pt-1 text-right">
                    <Button
                      variant="secondary"
                      disabled={done[l.line_no] || picked[l.line_no] == null || count >= MAX_LINES}
                      onClick={() => {
                        const c = l.candidates.find((x) => x.item_id === picked[l.line_no]);
                        if (c) add(l, c);
                      }}
                    >
                      선택한 품목 담기
                    </Button>
                  </div>
                </fieldset>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
