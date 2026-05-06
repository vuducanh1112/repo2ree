import type React from "react";
import { C, F, S_ACTION_BUTTON_BASE } from "../../../theme/theme";

export const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export const inputStyle = (
  locked: boolean,
  extra: React.CSSProperties = {},
): React.CSSProperties => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});
