import type React from "react";
import { S_SECTION_LABEL } from "./stylesCore";
import { C, F } from "./tokens";

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

export const S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  minWidth: 0,
  position: "relative",
  background: "linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 35%, #fff5f9 65%, #f4f8ff 100%)",
};

export const S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  pointerEvents: "none",
  zIndex: 0,
  overflow: "hidden",
};

export const S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT: React.CSSProperties = {
  position: "absolute",
  width: 480,
  height: 320,
  borderRadius: "50%",
  top: -80,
  left: "10%",
  background: "radial-gradient(ellipse, #c7d9ff88 0%, transparent 70%)",
};

export const S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT: React.CSSProperties = {
  position: "absolute",
  width: 360,
  height: 280,
  borderRadius: "50%",
  top: 20,
  right: "5%",
  background: "radial-gradient(ellipse, #e0d0ff66 0%, transparent 70%)",
};

export const S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER: React.CSSProperties = {
  position: "absolute",
  width: 300,
  height: 200,
  borderRadius: "50%",
  top: 160,
  left: "35%",
  background: "radial-gradient(ellipse, #ffd6e855 0%, transparent 70%)",
};

export const S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER: React.CSSProperties = {
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
