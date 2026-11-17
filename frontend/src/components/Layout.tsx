import { useEffect, useState } from "react";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { Link, Outlet } from "react-router-dom";
import { DISCLAIMER } from "../lib/format";
import ThemeToggle from "./ThemeToggle";
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
            <Link to="/evaluation" className="text-xs font-semibold text-brand-dark underline">평가 결과 보기</Link>
          </div>
          <ThemeToggle />
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
        <p className="mt-1">
          성남시 자료는 성남시 자원순환과가 작성하여 공공누리 제1유형(출처표시)으로 개방한 자료를 이용하였으며, 성남시 자원순환 통합 플랫폼(recycle.seongnam.go.kr)에서 확인할 수 있습니다. 확인일 2026-11-16.
        </p>
        <p className="mt-1">
          자료 이용 조건은 지자체마다 다릅니다. 선택한 지자체의 이용 조건과 확인일은 지자체 선택 화면과 결과 화면에서 확인하십시오. 표시한 내용은 지자체 페이지에 적힌 내용을 옮긴 것이며 법률 자문이 아닙니다.
        </p>
        <p className="mt-1">주소와 연락처 등 개인정보는 입력하지 마십시오. 견적은 30일 후 삭제됩니다.</p>
      </footer>
    </div>
  );
}
