import type React from "react";
import { C, F, S_SECTION_LABEL_SMALL, S_STATUS_BADGE_SM_BASE } from "../../../../constants/theme";

export const workflowSectionCardStyle = (active = false): React.CSSProperties => ({
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

export const SOURCE_CONFIG_LOCK_STYLE: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 7,
  padding: "6px 10px",
  borderRadius: 8,
  border: "1.5px solid #fde68a",
  background: "#fffbeb",
  color: "#92400e",
  fontSize: 12,
  fontFamily: F.sans,
  fontWeight: 700,
};

export const workflowStatusCardStyle = (
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

export const workflowStatusIconWrapStyle = (
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

export const workflowStatusKeyStyle = (
  isSet: boolean,
  accentColor: string,
): React.CSSProperties => ({
  ...S_SECTION_LABEL_SMALL,
  letterSpacing: 0.8,
  color: isSet ? accentColor : C.textMuted,
  opacity: 0.7,
  marginBottom: 1,
});

export const workflowStatusValueStyle = (
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

export const workflowStatusBadgeStyle = (accentColor: string): React.CSSProperties => ({
  ...S_STATUS_BADGE_SM_BASE,
  color: accentColor,
  background: `${accentColor}12`,
  border: `1px solid ${accentColor}40`,
});

type WorkflowTone = "warn" | "good" | "info";

const WORKFLOW_TONE = {
  warn: { bg: "#fffbeb", border: "#fde68a", icon: "#b45309", text: "#92400e" },
  good: { bg: "#f0fdf4", border: "#bbf7d0", icon: "#15803d", text: "#166534" },
  info: { bg: "#ecfeff", border: "#a5f3fc", icon: "#0e7490", text: "#155e75" },
} as const;

export const workflowTonePanelStyle = (tone: WorkflowTone): React.CSSProperties => {
  const toneStyle = WORKFLOW_TONE[tone];
  return {
    display: "flex",
    alignItems: "flex-start",
    gap: 6,
    padding: "4px 6px",
    borderRadius: 6,
    background: toneStyle.bg,
    border: `1px solid ${toneStyle.border}`,
  };
};

export const workflowToneIconStyle = (tone: WorkflowTone): React.CSSProperties => ({
  display: "flex",
  color: WORKFLOW_TONE[tone].icon,
  flexShrink: 0,
  marginTop: 1,
});

export const workflowToneTextStyle = (tone: WorkflowTone): React.CSSProperties => ({
  fontSize: 11,
  color: WORKFLOW_TONE[tone].text,
  lineHeight: 1.35,
});

export const workflowToneSurfaceStyle = (tone: WorkflowTone): React.CSSProperties => ({
  background: WORKFLOW_TONE[tone].bg,
  border: `1px solid ${WORKFLOW_TONE[tone].border}`,
  color: WORKFLOW_TONE[tone].text,
});

export const sourceIncludedLabelStyle = (enabled: boolean): React.CSSProperties => ({
  fontSize: 12,
  fontWeight: 700,
  color: enabled ? "#b45309" : C.textMid,
  fontFamily: F.sans,
});

export const sourceClearButtonTone = (locked: boolean): React.CSSProperties => ({
  border: "1.5px solid #fca5a5",
  background: "#fee2e2",
  color: "#991b1b",
  cursor: locked ? "not-allowed" : "pointer",
  opacity: locked ? 0.6 : 1,
});

export const runtimeFieldCardStyle = (isSet: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "10px 14px",
  background: isSet ? "#f0fdf4" : C.surfaceAlt,
  border: `1.5px solid ${isSet ? "#bbf7d0" : C.border}`,
  borderRadius: 8,
});

export const runtimeFieldIconWrapStyle = (isSet: boolean): React.CSSProperties => ({
  width: 28,
  height: 28,
  borderRadius: 7,
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: isSet ? "#dcfce7" : `${C.border}40`,
});

export const runtimeFieldIconColor = (isSet: boolean): string => (isSet ? "#16a34a" : C.textMuted);

export const runtimeFieldKeyStyle = (isSet: boolean): React.CSSProperties => ({
  fontSize: 10,
  textTransform: "uppercase",
  letterSpacing: 0.8,
  color: isSet ? "#16a34a" : C.textMuted,
  opacity: 0.7,
  marginBottom: 1,
  fontWeight: 700,
});

export const runtimeFieldValueStyle = (isSet: boolean): React.CSSProperties => ({
  fontSize: 12,
  fontWeight: 700,
  fontFamily: "JetBrains Mono, monospace",
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  color: isSet ? "#15803d" : C.textMuted,
});

export const runtimeSizeBadgeStyle = (isSet: boolean): React.CSSProperties => ({
  fontSize: 10,
  fontFamily: "JetBrains Mono, monospace",
  fontWeight: 700,
  color: isSet ? "#166534" : C.textMuted,
  background: isSet ? "#dcfce7" : C.surfaceAlt,
  border: `1px solid ${isSet ? "#86efac" : C.border}`,
  borderRadius: 4,
  padding: "2px 7px",
  flexShrink: 0,
});

export const runtimeIncludedWrapStyle = (isSet: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginLeft: 4,
  paddingLeft: 8,
  borderLeft: `1px solid ${isSet ? "#bbf7d0" : C.border}`,
});

export const runtimeIncludedLabelStyle = (included: boolean): React.CSSProperties => ({
  fontSize: 10,
  textTransform: "uppercase",
  letterSpacing: 0.7,
  color: included ? "#164e63" : C.textMuted,
  fontWeight: 700,
});

export const runtimeIncludedValueStyle = (included: boolean): React.CSSProperties => ({
  fontSize: 10,
  fontWeight: 700,
  color: included ? "#0891b2" : C.textMuted,
});

export const runtimeIncludedToggleTrackStyle = (included: boolean): React.CSSProperties => ({
  width: 34,
  height: 20,
  border: "none",
  borderRadius: 99,
  cursor: "pointer",
  background: included ? "#06b6d4" : C.borderMid,
  position: "relative",
});

export const runtimeIncludedToggleKnobStyle = (included: boolean): React.CSSProperties => ({
  position: "absolute",
  top: 2,
  left: included ? 16 : 2,
  width: 16,
  height: 16,
  borderRadius: "50%",
  background: "#fff",
  transition: "left 0.2s",
});

export const RUNTIME_STATUS_BADGE_STYLE: React.CSSProperties = {
  ...S_STATUS_BADGE_SM_BASE,
  color: "#16a34a",
  background: "#f0fdf4",
  border: "1px solid #bbf7d0",
};
