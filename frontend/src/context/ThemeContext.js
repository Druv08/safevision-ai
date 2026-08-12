import { createContext, useContext } from "react";

/* Context only — no components live in this file, so React Fast
   Refresh stays happy. The provider is in ThemeProvider.jsx. */
export const ThemeContext = createContext({
  theme: "dark",
  setTheme: () => {},
  toggleTheme: () => {},
  darkMode: true,
  setDarkMode: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}
