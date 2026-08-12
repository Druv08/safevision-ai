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

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.classList.toggle("light", theme === "light");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* non-fatal: the theme still applies for this session */
    }
  }, [theme]);

  const toggleTheme = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    []
  );

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      // Legacy aliases so older consumers keep working unchanged.
      darkMode: theme === "dark",
      setDarkMode: (on) => setTheme(on ? "dark" : "light"),
    }),
    [theme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
