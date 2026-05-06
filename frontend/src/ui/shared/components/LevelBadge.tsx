import { LEVELS } from "../../../core/review/levels";
import { F } from "../../theme/theme";

interface LevelBadgeProps {
  level: number;
  large?: boolean;
}

export function LevelBadge({ level, large = false }: LevelBadgeProps) {
  const levelMeta = LEVELS[Math.min(level, 7)];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: large ? 8 : 5,
        padding: large ? "6px 12px" : "3px 8px",
        background: levelMeta.bg,
        border: `1.5px solid ${levelMeta.color}40`,
        borderRadius: large ? 8 : 5,
      }}
    >
      <div
        style={{
          width: large ? 8 : 6,
          height: large ? 8 : 6,
          borderRadius: "50%",
          background: levelMeta.color,
          boxShadow: `0 0 6px ${levelMeta.color}80`,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          fontSize: large ? 13 : 11,
          fontWeight: 700,
          fontFamily: F.mono,
          color: levelMeta.color,
          letterSpacing: 0.4,
        }}
      >
        L{level} · {levelMeta.label}
      </span>
    </div>
  );
}
