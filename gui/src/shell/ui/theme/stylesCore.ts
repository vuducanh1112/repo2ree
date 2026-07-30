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

export const S_ACTION_BUTTON_BASE: React.CSSProperties = {
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "8px 12px",
  fontSize: 13,
  fontWeight: 600,
  fontFamily: F.sans,
  transition: "all 0.15s",
};

export const S_SEALED_META_ROW: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
};

export const S_SEALED_META_KEY: React.CSSProperties = {
  fontSize: 10,
  fontFamily: F.sans,
  color: C.textMuted,
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
