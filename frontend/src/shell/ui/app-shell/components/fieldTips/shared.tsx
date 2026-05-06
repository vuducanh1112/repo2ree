import type React from "react";
import { Ic } from "../../../shared/components/Icon";
import { C, F } from "../../../theme/theme";

export function tipTargetChip(active: boolean, idleLabel = "Click for tips"): React.ReactNode {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: F.sans,
        color: active ? C.accent : C.textMuted,
        background: active ? C.accentBg : C.surfaceAlt,
        border: `1px solid ${active ? C.accentBorder : C.border}`,
        borderRadius: 99,
        padding: "1px 7px",
        letterSpacing: 0.2,
      }}
    >
      {Ic.info(10)} {active ? "Tips open" : idleLabel}
    </span>
  );
}
