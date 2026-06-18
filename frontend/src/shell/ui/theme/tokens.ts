const TOKENS = {
  color: {
    bg: "#f4f6f9",
    surface: "#ffffff",
    surfaceAlt: "#f0f3f7",
    border: "#dde3ec",
    borderMid: "#c4cdd9",
    text: "#0d1117",
    textMid: "#4a5568",
    textMuted: "#8896a5",
    accent: "#2563eb",
    accentBg: "#eef4ff",
    accentBorder: "#bfdbfe",
    nav: "#111827",
    navBg: "#0f172a",
    navText: "#94a3b8",
    navActive: "#e2e8f0",
    error: "#dc2626",
    done: "#10b981",
  },
  font: {
    mono: "'JetBrains Mono', monospace",
    sans: "'Inter', system-ui, sans-serif",
  },
} as const;

export const C = TOKENS.color;
export const F = TOKENS.font;
