import { S_ACTION_BUTTON_BASE } from "@shell/ui/theme/theme";
import type React from "react";

export const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});
