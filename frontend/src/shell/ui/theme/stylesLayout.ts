import type React from "react";

export const S_FIELD_STACK_GAP_14: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 14,
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

export const S_WORKFLOW_PAGE_BODY: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  display: "flex",
  overflow: "hidden",
};

export const S_WORKFLOW_SERVICE_ROOT: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  flex: 1,
  minHeight: 0,
  overflow: "hidden",
  animation: "fadeUp 0.2s ease",
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
