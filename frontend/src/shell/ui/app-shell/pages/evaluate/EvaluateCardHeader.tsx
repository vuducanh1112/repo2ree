import { lgStyles } from "@shell/ui/theme/lightGlassTheme";

/** Shared label/hint header row used by the Evaluate result cards. */
export function CardHeader({ label, hint }: { label: string; hint?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        gap: 10,
        marginBottom: 10,
        flexWrap: "wrap",
      }}
    >
      <div style={lgStyles.label}>{label}</div>
      {hint && <span style={lgStyles.helper}>{hint}</span>}
    </div>
  );
}
