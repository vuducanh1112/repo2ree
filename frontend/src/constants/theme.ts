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
  },
  font: {
    mono: "'JetBrains Mono', monospace",
    sans: "'Inter', system-ui, sans-serif",
  },
} as const;

export const C = TOKENS.color;
export const F = TOKENS.font;

// ── Hover Helpers ─────────────────────────────────────────────────────────────
export const hoverBg = (enterBg: string, leaveBg: string) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.background = enterBg;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.background = leaveBg;
  },
});

export const hoverBorderColor = (enterBorder: string, leaveBorder: string) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.borderColor = enterBorder;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.borderColor = leaveBorder;
  },
});

export const hoverColor = (enterColor: string, leaveColor: string) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.color = enterColor;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.color = leaveColor;
  },
});

export const hoverBrightness = (brightnessPercent: number = 95) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.filter = `brightness(${brightnessPercent / 100})`;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.filter = "none";
  },
});

export const hoverIf = <T extends object>(condition: boolean, handlers: T): T | object =>
  condition ? handlers : {};

// ── Reusable Style Constants ───────────────────────────────────────────────────
export const S_SECTION_LABEL: React.CSSProperties = {
  fontSize: 12,
  letterSpacing: 1.2,
  color: C.textMuted,
  fontFamily: F.sans,
  textTransform: "uppercase",
  fontWeight: 700,
};

export const S_SECTION_LABEL_SMALL: React.CSSProperties = {
  ...S_SECTION_LABEL,
  fontSize: 10,
};

export const S_PANEL_HEADER_LABEL: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  color: C.text,
  letterSpacing: 0.3,
  fontFamily: F.sans,
};

export const S_OVERVIEW_PANEL_HEADER_ROW: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: `1px solid ${C.border}`,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

export const S_OVERVIEW_PANEL_FIELDS: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
};

export const S_OVERVIEW_PANEL_STATUS_ROW_BASE: React.CSSProperties = {
  marginLeft: "auto",
  display: "flex",
  alignItems: "center",
  gap: 6,
};

export const S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE: React.CSSProperties = {
  fontSize: 10,
  fontFamily: F.sans,
  fontWeight: 600,
  letterSpacing: 0.3,
};

export const S_OVERVIEW_PANEL_FOOTER: React.CSSProperties = {
  padding: "8px 12px",
  borderTop: `1px solid ${C.border}`,
};

export const S_ACTION_BUTTON_BASE: React.CSSProperties = {
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "8px 12px",
  fontSize: 13,
  fontWeight: 600,
  fontFamily: F.sans,
  transition: "all 0.15s",
};

export const S_OVERVIEW_PANEL_BUTTON_BASE: React.CSSProperties = {
  ...S_ACTION_BUTTON_BASE,
  fontSize: 11,
  borderRadius: 5,
  padding: "4px 8px",
  cursor: "pointer",
  textAlign: "center",
  width: "100%",
};

export const S_OVERVIEW_META_FOOTER: React.CSSProperties = {
  padding: "10px 12px",
  display: "flex",
  flexDirection: "column",
  gap: 7,
};

export const S_OVERVIEW_PANEL_BADGE_BASE: React.CSSProperties = {
  marginLeft: "auto",
  fontSize: 10,
  fontFamily: F.mono,
  borderRadius: 2,
  padding: "0 4px",
  letterSpacing: 0.8,
};

export const S_OVERVIEW_SEALED_META_ROW: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
};

export const S_OVERVIEW_SEALED_META_KEY: React.CSSProperties = {
  fontSize: 10,
  fontFamily: F.sans,
  color: C.textMuted,
  flexShrink: 0,
};

export const S_OVERVIEW_SEALED_ACTION_BTN_BASE: React.CSSProperties = {
  ...S_ACTION_BUTTON_BASE,
  marginTop: 6,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 7,
  width: "100%",
  padding: "8px 14px",
  fontSize: 12,
  fontWeight: 700,
  cursor: "pointer",
};

export const S_OVERVIEW_SEAL_STATUS_BADGE_BASE: React.CSSProperties = {
  fontSize: 10,
  fontFamily: F.mono,
  fontWeight: 700,
  borderRadius: 3,
  padding: "1px 6px",
  letterSpacing: 0.5,
  flexShrink: 0,
};

export const S_SOURCE_UPLOAD_STATUS_LINE_BASE: React.CSSProperties = {
  marginTop: 6,
  fontSize: 11,
  fontFamily: F.sans,
  display: "flex",
  alignItems: "center",
  gap: 4,
};

export const S_SOURCE_URL_STATUS_BASE: React.CSSProperties = {
  fontSize: 11,
  fontFamily: F.sans,
  display: "flex",
  alignItems: "center",
  gap: 4,
};

export const S_FIELD_ROW_BASE: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "220px 1fr",
  gap: 20,
  alignItems: "start",
  borderBottom: `1px solid ${C.border}`,
  margin: "0 -20px",
  padding: "18px 20px",
  transition: "background 0.15s",
  borderLeftWidth: 3,
  borderLeftStyle: "solid",
};

export const S_FIELD_ROW_HEAD: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 5,
  marginBottom: 3,
  flexWrap: "wrap",
};

export const S_FIELD_ROW_LABEL_BASE: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  fontFamily: F.sans,
};

export const S_FIELD_ROW_REQUIRED_BADGE: React.CSSProperties = {
  fontSize: 11,
  color: "#ef4444",
  fontWeight: 700,
  fontFamily: F.sans,
  background: "#fef2f2",
  border: "1px solid #fecaca",
  borderRadius: 3,
  padding: "1px 4px",
};

export const S_FIELD_ROW_DESC: React.CSSProperties = {
  fontSize: 13,
  color: C.textMuted,
  lineHeight: 1.5,
  margin: "0 0 5px",
};

export const S_FIELD_ROW_CONTENT: React.CSSProperties = {
  paddingTop: 2,
};

export const S_FIELD_STACK_GAP_14: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 14,
};

export const S_FIELD_STACK_GAP_5: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 5,
};

export const S_FIELD_HELP_TEXT_SMALL: React.CSSProperties = {
  fontSize: 11,
  color: C.textMuted,
  lineHeight: 1.4,
};

export const S_FLEX_ROW_GAP_8: React.CSSProperties = {
  display: "flex",
  gap: 8,
};

export const S_FLEX_ROW_CENTER_GAP_6: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
};

export const S_FLEX_COL_GAP_8: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 8,
};

export const S_FIELD_LABEL_TEXT_SM: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: C.textMid,
  fontFamily: F.sans,
};

export const S_TEXT_ITALIC_11: React.CSSProperties = {
  fontStyle: "italic",
  fontWeight: 400,
  fontSize: 11,
};

export const S_FIELD_TIP_CARD_BLOCK: React.CSSProperties = {
  marginBottom: 16,
};

export const S_FIELD_TIP_CARD_BLOCK_LABEL: React.CSSProperties = {
  ...S_SECTION_LABEL,
  letterSpacing: 0.8,
  marginBottom: 6,
};

export const S_FIELD_TIP_CARD_COMMANDS_LABEL: React.CSSProperties = {
  ...S_SECTION_LABEL,
  letterSpacing: 0.8,
  marginBottom: 8,
};

export const S_RUNTIME_PICKER_WRAP: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
};

export const S_RUNTIME_HELP_TEXT: React.CSSProperties = {
  fontSize: 11,
  color: C.textMuted,
  lineHeight: 1.5,
};

export const S_WORKFLOW_PAGE_ROOT: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
  minHeight: 0,
  overflow: "hidden",
};

export const S_WORKFLOW_PAGE_BODY: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  display: "flex",
  overflow: "hidden",
};

export const S_WORKFLOW_PAGE_MAIN_SCROLL: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: 28,
  minWidth: 0,
};

export const S_WORKFLOW_PAGE_MAIN_COL: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 20,
};

export const S_WORKFLOW_PAGE_NUDGE_WRAP: React.CSSProperties = {
  padding: "0 24px 24px",
  flexShrink: 0,
};

export const S_WORKFLOW_SERVICE_ROOT: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  flex: 1,
  minHeight: 0,
  overflow: "hidden",
  animation: "fadeUp 0.2s ease",
};

export const S_WORKFLOW_SERVICE_MAIN_SCROLL: React.CSSProperties = {
  flex: 1,
  overflowY: "auto",
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
  padding: "24px 28px",
  gap: 16,
};

export const S_EXPLORER_MAIN_CONTENT_ROOT: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  minWidth: 0,
  position: "relative",
  background: "linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 35%, #fff5f9 65%, #f4f8ff 100%)",
};

export const S_EXPLORER_MAIN_CONTENT_BG_LAYER: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  pointerEvents: "none",
  zIndex: 0,
  overflow: "hidden",
};

export const S_EXPLORER_MAIN_CONTENT_BG_BLOB_LEFT: React.CSSProperties = {
  position: "absolute",
  width: 480,
  height: 320,
  borderRadius: "50%",
  top: -80,
  left: "10%",
  background: "radial-gradient(ellipse, #c7d9ff88 0%, transparent 70%)",
};

export const S_EXPLORER_MAIN_CONTENT_BG_BLOB_RIGHT: React.CSSProperties = {
  position: "absolute",
  width: 360,
  height: 280,
  borderRadius: "50%",
  top: 20,
  right: "5%",
  background: "radial-gradient(ellipse, #e0d0ff66 0%, transparent 70%)",
};

export const S_EXPLORER_MAIN_CONTENT_BG_BLOB_CENTER: React.CSSProperties = {
  position: "absolute",
  width: 300,
  height: 200,
  borderRadius: "50%",
  top: 160,
  left: "35%",
  background: "radial-gradient(ellipse, #ffd6e855 0%, transparent 70%)",
};

export const S_EXPLORER_MAIN_CONTENT_INNER: React.CSSProperties = {
  position: "relative",
  zIndex: 1,
  flex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  minWidth: 0,
};

export const S_WORKFLOW_PAGE_SCRIPTS_WRAP: React.CSSProperties = {
  padding: "16px 24px 0",
  flexShrink: 0,
};

export const S_WORKFLOW_PAGE_LOG_WRAP: React.CSSProperties = {
  padding: "4px 0 24px",
  flex: 1,
  display: "flex",
  flexDirection: "column",
  minHeight: 0,
};

export const S_WORKFLOW_BUILD_SECTION_WRAP: React.CSSProperties = {
  padding: "16px 24px",
  borderBottom: `1px solid ${C.border}`,
  flexShrink: 0,
};

export const S_STATUS_BADGE_SM_BASE: React.CSSProperties = {
  fontSize: 10,
  fontFamily: F.sans,
  fontWeight: 700,
  borderRadius: 4,
  padding: "2px 7px",
  flexShrink: 0,
};

export const S_TEXT_MUTED_11: React.CSSProperties = {
  fontSize: 11,
  color: C.textMuted,
};

export const S_SECTION_LABEL_MB12: React.CSSProperties = {
  ...S_SECTION_LABEL,
  marginBottom: 12,
};

export const S_SCRIPT_VIEW_MESSAGE_BASE: React.CSSProperties = {
  padding: "12px 16px",
  fontSize: 12,
  fontFamily: F.mono,
};
