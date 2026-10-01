const THEME_STORAGE_KEY = "debrief.theme";

let themeStarted = false;

export type ThemeChoice = "light" | "dark";

export function readStoredTheme(): ThemeChoice | null {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return null;
}

export function storeTheme(theme: ThemeChoice) {
  localStorage.setItem(THEME_STORAGE_KEY, theme);
  applyTheme(theme);
}

export function startTheme() {
  applyResolvedTheme();
  if (themeStarted) {
    return;
  }
  themeStarted = true;
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (readStoredTheme() === null) {
        applyResolvedTheme();
      }
    });
}

function applyResolvedTheme() {
  applyTheme(readStoredTheme() ?? systemTheme());
}

function systemTheme(): ThemeChoice {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme(theme: ThemeChoice) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}
