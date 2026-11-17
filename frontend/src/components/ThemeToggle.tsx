import { useState } from "react";
import { applyTheme, currentTheme } from "../lib/theme";

/** 화면 색상을 라이트/다크로 바꾸는 버튼. 선택은 이 브라우저에 저장된다. */
export default function ThemeToggle() {
  const [dark, setDark] = useState(() => currentTheme() === "dark");

  function toggle() {
    const next = dark ? "light" : "dark";
    applyTheme(next, true);
    setDark(next === "dark");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      className="ml-auto inline-flex min-h-11 shrink-0 items-center whitespace-nowrap rounded-xl border border-line px-3 text-sm font-semibold text-ink hover:bg-brand-soft"
    >
      {dark ? "라이트 모드" : "다크 모드"}
    </button>
  );
}
