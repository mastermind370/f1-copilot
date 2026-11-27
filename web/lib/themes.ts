// School color themes. `primary` carries white text (buttons, active tabs, brand mark), so
// for schools whose signature color is a light gold or maize, the dark partner color is the
// primary and the gold becomes the accent. Hex values follow each university's public brand
// guidelines; re-check them if a school updates its palette.
//
// Only colors are used. No logos, wordmarks or mascots appear anywhere in the app.

export interface Theme {
  primary: string;
  accent: string;
}

export const DEFAULT_THEME: Theme = { primary: "#2a3bb8", accent: "#f2a93b" };

export const THEMES: Record<string, Theme> = {
  illinois: { primary: "#13294b", accent: "#ff5f05" },
  indiana: { primary: "#990000", accent: "#c9a66b" },
  iowa: { primary: "#1f1f1f", accent: "#ffcd00" },
  maryland: { primary: "#c8102e", accent: "#ffd200" },
  michigan: { primary: "#00274c", accent: "#ffcb05" },
  "michigan-state": { primary: "#18453b", accent: "#7bbd00" },
  minnesota: { primary: "#7a0019", accent: "#ffcc33" },
  nebraska: { primary: "#d00000", accent: "#c8a882" },
  northwestern: { primary: "#4e2a84", accent: "#b6acd1" },
  "ohio-state": { primary: "#bb0000", accent: "#a7b1b7" },
  oregon: { primary: "#154733", accent: "#fee123" },
  "penn-state": { primary: "#001e44", accent: "#1e407c" },
  purdue: { primary: "#1f1f1f", accent: "#cfb991" },
  rutgers: { primary: "#cc0033", accent: "#5f6a72" },
  ucla: { primary: "#005587", accent: "#ffd100" },
  usc: { primary: "#990000", accent: "#ffcc00" },
  washington: { primary: "#4b2e83", accent: "#b7a57a" },
  wisconsin: { primary: "#c5050c", accent: "#646569" },
  nyu: { primary: "#57068c", accent: "#8900e1" },
};

export function themeFor(schoolId: string | null | undefined): Theme {
  return (schoolId && THEMES[schoolId]) || DEFAULT_THEME;
}

/** Writes the theme into CSS custom properties; every other color is derived in CSS. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement.style;
  root.setProperty("--primary", theme.primary);
  root.setProperty("--accent", theme.accent);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme.primary);
}
