import type React from "react";
import { C, F } from "./tokens";

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
