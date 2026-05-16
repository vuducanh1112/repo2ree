import type React from "react";
import { lgColors } from "../../../theme/lightGlassTheme";
import { F, S_ACTION_BUTTON_BASE } from "../../../theme/theme";

export const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export const inp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties => ({
  width: "100%",
  border: "1px solid rgba(95, 142, 190, 0.42)",
  borderRadius: 7,
  padding: "8px 11px",
  fontSize: 13,
  fontFamily: F.mono,
  color: locked ? lgColors.textMuted : lgColors.text,
  background: locked ? "rgba(241, 245, 249, 0.72)" : "rgba(255, 255, 255, 0.72)",
  boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.92)",
  outline: "none",
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

export const selectInp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties =>
  inp(locked, extra);
