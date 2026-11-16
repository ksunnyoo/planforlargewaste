import { feeLabel, SPEC_MISSING } from "../lib/format";
import { MAX_LINES, useDraftStore } from "../store/draftStore";
import { Badge, Button, Card, Icon } from "./ui";

export default function DraftList({ onSubmit, submitting }: { onSubmit: () => void; submitting: boolean }) {
  const lines = useDraftStore((s) => s.lines);
  const setQuantity = useDraftStore((s) => s.setQuantity);
  const setOperatorFee = useDraftStore((s) => s.setOperatorFee);
  const removeLine = useDraftStore((s) => s.removeLine);

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-bold">3. 담은 품목 확인</h2>
        <span className="text-xs text-muted">{lines.length} / {MAX_LINES}개</span>
      </div>

      {lines.length === 0 ? (
        <p className="mt-3 rounded-xl bg-slate-50 px-3 py-6 text-center text-sm text-muted">아직 담은 품목이 없습니다. 위에서 검색해 담으십시오.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {lines.map((l) => (
            <li key={l.itemId} className="rounded-xl border border-line p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{l.name}</p>
                  <p className="text-xs text-muted">{l.spec === SPEC_MISSING ? "규격 미기재" : l.spec}</p>
                  <div className="mt-1 text-xs">
                    단가{" "}
                    {l.feeType === "paid" ? (
                      <b>{feeLabel(l.feeType, l.unitFeeWon)}</b>
                    ) : (
                      <Badge tone={l.feeType === "free" ? "ok" : "info"}>{feeLabel(l.feeType, 0)}</Badge>
                    )}
                  </div>
                </div>
                <Button variant="ghost" className="px-2" onClick={() => removeLine(l.itemId)} aria-label={`${l.name} 삭제`}>
                  <Icon name="trash" />
                </Button>
              </div>
              <div className="mt-3 flex flex-wrap items-end gap-4">
                <div>
                  <p id={`q-${l.itemId}`} className="mb-1 text-xs font-semibold text-muted">수량</p>
                  <div className="flex items-center gap-1" role="group" aria-labelledby={`q-${l.itemId}`}>
                    <Button variant="secondary" className="w-11 px-0" onClick={() => setQuantity(l.itemId, l.quantity - 1)} disabled={l.quantity <= 1} aria-label="수량 줄이기">
                      <Icon name="minus" />
                    </Button>
                    <input
                      inputMode="numeric"
                      value={l.quantity}
                      onChange={(e) => setQuantity(l.itemId, Number(e.target.value.replace(/\D/g, "")))}
                      className="min-h-11 w-14 rounded-xl border border-line text-center text-sm font-semibold"
                      aria-label="수량"
                    />
                    <Button variant="secondary" className="w-11 px-0" onClick={() => setQuantity(l.itemId, l.quantity + 1)} disabled={l.quantity >= 99} aria-label="수량 늘리기">
                      <Icon name="plus" />
                    </Button>
                  </div>
                </div>
                <div className="min-w-40 flex-1">
                  <label htmlFor={`op-${l.itemId}`} className="mb-1 block text-xs font-semibold text-muted">
                    업체 작업비 (선택, 원)
                  </label>
                  <input
                    id={`op-${l.itemId}`}
                    inputMode="numeric"
                    value={l.operatorFeeWon === 0 ? "" : l.operatorFeeWon.toLocaleString("ko-KR")}
                    onChange={(e) => setOperatorFee(l.itemId, Number(e.target.value.replace(/\D/g, "")))}
                    placeholder="0"
                    className="min-h-11 w-full rounded-xl border border-line px-3 text-right text-sm"
                  />
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Button className="mt-4 w-full" onClick={onSubmit} disabled={lines.length === 0 || submitting}>
        {submitting ? "견적을 계산하고 있습니다. 잠시 기다려 주십시오." : "견적 확인하기"}
      </Button>
      <p className="mt-2 text-center text-xs text-muted">지자체 수수료는 서버에 저장된 기준 단가로 계산합니다.</p>
    </Card>
  );
}
