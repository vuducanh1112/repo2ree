import type React from "react";
import type { ReeAssemblyBadge } from "../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../shared/components/Icon";
import { C, F, S_ACTION_BUTTON_BASE } from "../../theme/theme";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

interface AssemblyPageHeaderProps {
  color: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  tips?: string[];
  runDone?: boolean;
  badge?: ReeAssemblyBadge | null;
  ts?: string;
  timestampPrefix?: string;
  missingCount?: number;
  onGoFields?: () => void;
  rightAction?: React.ReactNode;
}
export function AssemblyPageHeader({
  color,
  icon,
  title,
  subtitle,
  tips = [],
  runDone,
  badge,
  ts,
  timestampPrefix = "Last run",
  missingCount = 0,
  onGoFields,
  rightAction,
}: AssemblyPageHeaderProps) {
  return (
    <div
      style={{
        flexShrink: 0,
        padding: "16px 28px 14px",
        borderBottom: `1px solid ${C.border}`,
        background: "rgba(255,255,255,0.7)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: `${color}18`,
          color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: C.text, letterSpacing: -0.2 }}>
            {title}
          </span>
          {runDone && badge && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: badge.color,
                background: badge.bg,
                border: `1px solid ${badge.color}40`,
                borderRadius: 99,
                padding: "2px 9px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {Ic.check(10)} {badge.label}
            </span>
          )}
          {missingCount > 0 && onGoFields && (
            <button
              type="button"
              style={{
                ...actionBtn({
                  fontSize: 11,
                  borderRadius: 99,
                  padding: "2px 9px",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#dc2626",
                  transition: "all 0.12s",
                }),
                display: "flex",
                alignItems: "center",
                gap: 4,
                cursor: "pointer",
              }}
              onClick={onGoFields}
            >
              {Ic.info(10)} {missingCount} missing field{missingCount > 1 ? "s" : ""} ← fix
            </button>
          )}
        </div>
        <div style={{ fontSize: 12, color: C.textMuted, marginTop: 1 }}>{subtitle}</div>
        {tips.length > 0 && (
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 3 }}>
            {tips.map((tip) => (
              <div
                key={tip}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 6,
                  fontSize: 11,
                  color: C.textMid,
                  lineHeight: 1.4,
                  fontFamily: F.sans,
                }}
              >
                <span style={{ color, display: "flex", marginTop: 1, flexShrink: 0 }}>
                  {Ic.info(10)}
                </span>
                <span>{tip}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {rightAction}
      {runDone && ts && (
        <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>
          {timestampPrefix}{" "}
          {new Date(ts).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      )}
    </div>
  );
}
