import { useEffect, useState } from "react";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { Link, Outlet } from "react-router-dom";
import { DISCLAIMER } from "../lib/format";
import { Banner, Icon } from "./ui";

/** 요청이 5초 넘게 끝나지 않으면 서버 시작 안내를 보여 준다(무료 서버 절전 대비). */
function ServerWakeNotice() {
  const busy = useIsFetching() + useIsMutating() > 0;
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!busy) {
      setSlow(false);
      return;
    }
    const t = setTimeout(() => setSlow(true), 5000);
    return () => clearTimeout(t);
  }, [busy]);
  if (!slow) return null;
  return (
    <div className="no-print">
      <Banner tone="info">서버를 시작하고 있습니다. 최대 1분 정도 걸릴 수 있습니다.</Banner>
    </div>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen">
      <header className="no-print border-b border-line bg-white">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-4">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-white">
            <Icon name="pin" className="h-5 w-5" />
          </span>
          <div>
            <Link to="/" className="block text-lg font-bold leading-tight text-ink">
              대형폐기물 배출 플래너
            </Link>
            <p className="text-xs text-muted">수수료 계산과 배출 절차를 한 화면에서 확인하십시오.</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6">
        <ServerWakeNotice />
        <Outlet />
      </main>

      <footer className="mx-auto max-w-3xl px-4 pb-10 text-xs leading-relaxed text-muted">
        <p className="font-semibold text-slate-600">{DISCLAIMER}</p>
        <p className="mt-1">
          수수료는 전국 대형폐기물 수수료 표준데이터(공공데이터포털)와 성남시 조례 별표를 기준으로 하며, 지자체마다 기준일이 다릅니다.
        </p>
        <p className="mt-1">주소와 연락처 등 개인정보는 입력하지 마십시오. 견적은 30일 후 삭제됩니다.</p>
      </footer>
    </div>
  );
}
