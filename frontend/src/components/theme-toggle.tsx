import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { storeTheme } from "@/lib/theme.ts";

export function ThemeToggle() {
  const theme = useAppliedTheme();

  return (
    <Button
      variant="ghost"
      className="text-sm motion-reduce:transition-none motion-reduce:active:translate-y-0"
      onClick={() => storeTheme(theme === "dark" ? "light" : "dark")}
    >
      {theme === "dark"
        ? (
            <>
              <Sun className="size-4" />
              {" "}
              Use light
            </>
          )
        : (
            <>
              <Moon className="size-4" />
              {" "}
              Use dark
            </>
          )}
    </Button>
  );
}

function useAppliedTheme() {
  return useSyncExternalStore(
    subscribeThemeClass,
    readThemeClass,
    () => "light" as const,
  );
}

function readThemeClass() {
  return document.documentElement.classList.contains("dark")
    ? ("dark" as const)
    : ("light" as const);
}

function subscribeThemeClass(listener: () => void) {
  const observer = new MutationObserver(listener);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}
