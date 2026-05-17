import type React from "react";
import { C, F, S_SECTION_LABEL_SMALL, S_STATUS_BADGE_SM_BASE } from "../../theme/theme";

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

export const assemblyStatusCardStyle = (
  isSet: boolean,
  accentColor: string,
): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "10px 14px",
  background: isSet ? `${accentColor}12` : C.surfaceAlt,
  border: `1.5px solid ${isSet ? `${accentColor}40` : C.border}`,
  borderRadius: 9,
});

export const assemblyStatusIconWrapStyle = (
  isSet: boolean,
  accentColor: string,
): React.CSSProperties => ({
  width: 28,
  height: 28,
  borderRadius: 7,
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: isSet ? `${accentColor}18` : `${C.border}40`,
});

export const assemblyStatusKeyStyle = (
  isSet: boolean,
  accentColor: string,
): React.CSSProperties => ({
  ...S_SECTION_LABEL_SMALL,
  letterSpacing: 0.8,
  color: isSet ? accentColor : C.textMuted,
  opacity: 0.7,
  marginBottom: 1,
});

export const assemblyStatusValueStyle = (
  isSet: boolean,
  accentColor: string,
): React.CSSProperties => ({
  fontSize: 12,
  fontWeight: 700,
  fontFamily: F.mono,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  color: isSet ? accentColor : C.textMuted,
});

export const assemblyStatusBadgeStyle = (accentColor: string): React.CSSProperties => ({
  ...S_STATUS_BADGE_SM_BASE,
  color: accentColor,
  background: `${accentColor}12`,
  border: `1px solid ${accentColor}40`,
});

export const RUNTIME_STATUS_BADGE_STYLE: React.CSSProperties = {
  ...S_STATUS_BADGE_SM_BASE,
  color: "#16a34a",
  background: "#f0fdf4",
  border: "1px solid #bbf7d0",
};
