import { useCallback, useEffect, useMemo, useState } from "react";
import { ThemeContext } from "./ThemeContext";

const STORAGE_KEY = "theme";

function readInitialTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* storage blocked (private mode) — fall through to the default */
  }
  // The product is designed around the dark industrial palette, so
  // that stays the default until the user picks otherwise.
  return "dark";
}

// Applied in the change handler as well as the effect, so components that read
// CSS tokens during the re-render (chart colours) already see the new theme.
function applyTheme(theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.classList.toggle("light", theme === "light");
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readInitialTheme);

  const setTheme = useCallback((t) => { applyTheme(t); setThemeState(t); }, []);

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* non-fatal: the theme still applies for this session */
    }
  }, [theme]);

  const toggleTheme = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      // Legacy aliases so older consumers keep working unchanged.
      darkMode: theme === "dark",
      setDarkMode: (on) => setTheme(on ? "dark" : "light"),
    }),
    [theme, setTheme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
