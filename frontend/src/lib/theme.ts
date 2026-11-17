export type Theme = "light" | "dark";

const KEY = "plw-theme";

/** 저장된 선택. 브라우저 저장소를 쓸 수 없으면(차단 등) null. */
export function readStoredTheme(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "dark" || v === "light" ? v : null;
  } catch {
    return null;
  }
}

export function systemTheme(): Theme {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** 화면에 적용된 테마(index.html의 첫 스크립트가 먼저 정한다). */
export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function applyTheme(theme: Theme, persist: boolean): void {
  document.documentElement.dataset.theme = theme;
  if (!persist) return;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* 저장하지 못해도 현재 화면에는 적용된다. */
  }
}
