import type React from "react";
import { S_ACTION_BUTTON_BASE } from "../../theme/theme";

export const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});
