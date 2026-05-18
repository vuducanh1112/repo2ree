import type { ReeAssemblyRequirement } from "../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgInfoBanner } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";

interface MissingInputsBannerProps {
  missing: ReeAssemblyRequirement[];
  onGoFields?: () => void;
}

export function MissingInputsBanner({ missing, onGoFields }: MissingInputsBannerProps) {
  if (missing.length === 0) return null;
  return (
    <div style={{ ...lgInfoBanner("danger"), flexDirection: "column", alignItems: "stretch" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: lgColors.danger }}>
          Required inputs missing
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {missing.map((item) => (
          <span
            key={item.field}
            style={{
              fontSize: 11,
              fontFamily: F.sans,
              color: lgColors.danger,
              background: "rgba(255,255,255,0.55)",
              border: `1px solid ${lgColors.dangerBorder}`,
              borderRadius: 4,
              padding: "2px 8px",
            }}
          >
            {item.label}
          </span>
        ))}
      </div>
      {onGoFields && (
        <button
          type="button"
          onClick={onGoFields}
          style={{
            alignSelf: "flex-start",
            fontSize: 11,
            fontWeight: 700,
            border: `1px solid ${lgColors.dangerBorder}`,
            background: "rgba(255,255,255,0.6)",
            color: lgColors.danger,
            borderRadius: 6,
            padding: "4px 10px",
            cursor: "pointer",
          }}
        >
          Jump to required field
        </button>
      )}
    </div>
  );
}
