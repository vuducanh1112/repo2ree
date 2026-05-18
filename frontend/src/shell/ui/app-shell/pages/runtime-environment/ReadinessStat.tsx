import { lgColors, lgReadout, lgStyles } from "../../../theme/lightGlassTheme";

export function ReadinessStat({ label, done }: { label: string; done: boolean }) {
  return (
    <div style={lgReadout(lgStyles.statReadout)}>
      <span style={{ color: lgColors.textMuted, fontSize: 11 }}>{label}</span>
      <strong style={{ color: lgColors.text, fontSize: 18 }}>{done ? "✓" : "—"}</strong>
    </div>
  );
}
