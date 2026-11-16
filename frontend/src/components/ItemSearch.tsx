import { useState } from "react";
import { useItemSearch } from "../api/hooks";
import { feeLabel, SPEC_MISSING } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";
import { MAX_LINES, useDraftStore } from "../store/draftStore";
import { Badge, Button, Card, ErrorBox, Icon, LineCardSkeleton } from "./ui";

export default function ItemSearch() {
  const code = useDraftStore((s) => s.municipalityCode);
  const addItem = useDraftStore((s) => s.addItem);
  const count = useDraftStore((s) => s.lines.length);
  const [q, setQ] = useState("");
  const term = useDebounced(q, 300);
  const { data, isFetching, isError, error, refetch } = useItemSearch(code, term);
  const waiting = q.trim().length > 0 && (isFetching || q !== term) && !data;

  if (!code) return null;
  return (
    <Card>
      <label htmlFor="item-q" className="text-sm font-bold">
        2. 버리실 물건을 검색해 담으십시오.
      </label>
      <p className="mt-1 text-xs text-muted">물건 이름을 한 번에 하나씩 입력하십시오. 규격이 여러 개이면 알맞은 규격을 담으십시오.</p>
      <div className="relative mt-2">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
          <Icon name="search" />
        </span>
        <input
          id="item-q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={50}
          placeholder="예: 책상, 소파, 냉장고"
          className="min-h-11 w-full rounded-xl border border-line bg-white pl-9 pr-3 text-sm"
          autoComplete="off"
        />
      </div>

      <div className="mt-3 space-y-2" aria-live="polite">
        {waiting && (
          <>
            <LineCardSkeleton />
            <LineCardSkeleton />
          </>
        )}
        {isError && <ErrorBox message={error.message} onRetry={() => refetch()} />}
        {data && data.length === 0 && q.trim() && !isFetching && (
          <p className="rounded-xl bg-slate-50 px-3 py-4 text-center text-sm text-muted">
            일치하는 품목이 없습니다. 다른 이름으로 검색하십시오. 해당 지자체 표에 없는 품목은 지자체에 문의하십시오.
          </p>
        )}
        {data?.map((it) => (
          <div key={it.item_id} className="flex items-center justify-between gap-3 rounded-xl border border-line p-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{it.name}</p>
              <p className="text-xs text-muted">
                {it.spec === SPEC_MISSING ? <span className="text-warn">규격이 기재되지 않았습니다. 해당 지자체에 확인하십시오.</span> : it.spec}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <div className="text-right">
                {it.fee_type === "paid" ? (
                  <p className="text-sm font-bold">{feeLabel(it.fee_type, it.fee_won)}</p>
                ) : (
                  <Badge tone={it.fee_type === "free" ? "ok" : "info"}>{feeLabel(it.fee_type, it.fee_won)}</Badge>
                )}
              </div>
              <Button variant="secondary" className="px-3" onClick={() => addItem(it)} disabled={count >= MAX_LINES} aria-label={`${it.name} ${it.spec} 담기`}>
                <Icon name="plus" /> 담기
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
