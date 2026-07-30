import { lgColors } from "../../theme/lightGlassTheme";
import { F } from "../../theme/theme";

export function LastRunStamp({ label, ts }: { label: string; ts: string }) {
  return (
    <span
      style={{
        fontSize: 11,
        color: lgColors.textMuted,
        fontFamily: F.mono,
        flexShrink: 0,
      }}
    >
      {label}{" "}
      {new Date(ts).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}
