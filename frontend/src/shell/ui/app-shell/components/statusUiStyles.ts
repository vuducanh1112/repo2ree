import type React from "react";
import { C, F } from "../../theme/theme";

export const assemblySectionCardStyle = (active = false): React.CSSProperties => ({
  border: `1.5px solid ${active ? C.accentBorder : C.border}`,
  background: C.surface,
  borderRadius: 10,
  padding: 14,
  display: "flex",
  flexDirection: "column",
  gap: 10,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  transition: "border-color 0.2s, box-shadow 0.2s",
});

export const WORKFLOW_LOG_PANEL_ROOT_STYLE: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  background: C.surface,
  borderRadius: 10,
  border: `1px solid ${C.border}`,
  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  minHeight: 200,
  maxHeight: 360,
};

export const WORKFLOW_LOG_PANEL_HEADER_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  padding: "11px 20px",
  fontSize: 11,
  color: C.textMuted,
  fontFamily: F.mono,
  borderBottom: `1px solid ${C.border}`,
  background: "#fafbfd",
  flexShrink: 0,
};

export const WORKFLOW_LOG_EMPTY_STYLE: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  minHeight: 200,
  gap: 8,
  color: C.textMuted,
};
