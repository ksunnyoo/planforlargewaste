import { useMemo, useState } from "react";
import { useMunicipalities } from "../api/hooks";
import type { Municipality } from "../api/types";
import { dateKo } from "../lib/format";
import { useDraftStore } from "../store/draftStore";
import { Badge, Banner, Button, Card, ErrorBox, Icon, Skeleton } from "./ui";

export function SupportBadge({ m }: { m: Municipality }) {
  return m.support_level === "fee_and_procedure" ? (
    <Badge tone="ok" icon={<Icon name="check" className="h-3 w-3" />}>수수료 + 절차 안내</Badge>
  ) : (
    <Badge tone="gray">수수료만 제공</Badge>
  );
}

/** 선택한 지자체에 대한 안내(수준·규격 누락·기준일). 입력·결과 화면에서 함께 쓴다. */
export function MunicipalityNotices({ m }: { m: Municipality }) {
  return (
    <div className="space-y-2">
      {m.support_level === "fee_only" && (
        <Banner tone="info">
          이 지역은 수수료만 제공합니다. 절차는 해당 지자체의 안내를 확인하십시오. 데이터 품질(누락·표기 차이)은 성남시보다 덜 검증되었습니다.
        </Banner>
      )}
      {m.spec_missing && (
        <Banner tone="warn" title="규격 정보가 제공되지 않습니다.">
          수수료는 참고용이며 해당 지자체에 확인하십시오.
        </Banner>
      )}
    </div>
  );
}

export default function MunicipalityPicker() {
  const { data, isPending, isError, error, refetch } = useMunicipalities();
  const code = useDraftStore((s) => s.municipalityCode);
  const setMunicipality = useDraftStore((s) => s.setMunicipality);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(false);

  const selected = data?.find((m) => m.code === code) ?? null;
  const shown = useMemo(() => {
    const f = filter.replace(/\s+/g, "");
    return (data ?? []).filter((m) => m.name.replace(/\s+/g, "").includes(f));
  }, [data, filter]);

  if (isPending)
    return (
      <Card>
        <Skeleton className="mb-3 h-5 w-32" />
        <Skeleton className="h-11 w-full" />
      </Card>
    );
  if (isError) return <ErrorBox message={error.message} onRetry={() => refetch()} />;

  if (selected && !open)
    return (
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-muted">1. 지자체</p>
            <p className="mt-0.5 text-lg font-bold">{selected.name}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <SupportBadge m={selected} />
              <span className="text-xs text-muted">
                {selected.legal_effective_date ? "데이터 확인일" : "수수료 기준일"} {dateKo(selected.data_base_date)}
                {selected.legal_effective_date && ` · 조례 시행일 ${dateKo(selected.legal_effective_date)}`}
              </span>
            </div>
          </div>
          <Button variant="secondary" className="no-print" onClick={() => setOpen(true)}>
            변경
          </Button>
        </div>
        <div className="mt-3">
          <MunicipalityNotices m={selected} />
        </div>
      </Card>
    );

  return (
    <Card>
      <label htmlFor="muni-filter" className="text-sm font-bold">
        1. 지자체를 선택하십시오.
      </label>
      <div className="relative mt-2">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
          <Icon name="search" />
        </span>
        <input
          id="muni-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="지자체 이름으로 찾기 (예: 성남, 수원)"
          className="min-h-11 w-full rounded-xl border border-line bg-white pl-9 pr-3 text-sm"
        />
      </div>
      <ul className="mt-3 max-h-72 space-y-1 overflow-y-auto pr-1" aria-label="지자체 목록">
        {shown.map((m) => (
          <li key={m.code}>
            <button
              type="button"
              onClick={() => {
                setMunicipality(m.code);
                setOpen(false);
                setFilter("");
              }}
              className="flex w-full flex-wrap items-center justify-between gap-2 rounded-xl border border-transparent px-3 py-2.5 text-left hover:border-line hover:bg-brand-soft"
            >
              <span className="text-sm font-medium">{m.name}</span>
              <span className="flex items-center gap-1.5">
                {m.spec_missing && <Badge tone="warn">규격 정보 없음</Badge>}
                <SupportBadge m={m} />
              </span>
            </button>
          </li>
        ))}
        {shown.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">일치하는 지자체가 없습니다. 지원하지 않는 지역일 수 있습니다.</li>}
      </ul>
      {selected && (
        <Button variant="ghost" className="mt-2" onClick={() => setOpen(false)}>
          선택 유지
        </Button>
      )}
    </Card>
  );
}
