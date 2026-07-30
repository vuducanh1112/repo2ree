import type { Threat, ThreatCategory, ThreatSeverity } from "@core/evaluate/Threat";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgContentCard } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { CardHeader } from "./RepoAnalysisCardHeader";

const THREAT_DIMENSIONS: { category: ThreatCategory; label: string }[] = [
  { category: "dependency", label: "Dependency declaration" },
  { category: "environment", label: "Environment capture" },
  { category: "machine", label: "Machine capture" },
];

const SEVERITY_META: Record<
  ThreatSeverity,
  { label: string; color: string; bg: string; border: string }
> = {
  high: { label: "high", color: "#dc2626", bg: "#fef2f2", border: "#fca5a5" },
  medium: { label: "medium", color: "#d97706", bg: "#fffbeb", border: "#fcd34d" },
  low: { label: "low", color: "#0369a1", bg: "#f0f9ff", border: "#7dd3fc" },
};

function ThreatRow({ threat }: { threat: Threat }) {
  const meta = SEVERITY_META[threat.severity];
  return (
    <div
      style={{
        border: `1px solid ${threat.blocking ? meta.border : "rgba(148,163,184,0.32)"}`,
        background: threat.blocking ? meta.bg : "rgba(255,255,255,0.55)",
        borderRadius: 9,
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: 0.3,
            color: meta.color,
            background: meta.bg,
            border: `1px solid ${meta.border}`,
            borderRadius: 99,
            padding: "2px 8px",
            fontFamily: F.mono,
          }}
        >
          {meta.label}
        </span>
        <span style={{ fontSize: 11, color: lgColors.textMuted, fontFamily: F.mono }}>
          {threat.category}
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: lgColors.text }}>{threat.title}</span>
        {threat.blocking && (
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              fontWeight: 800,
              color: meta.color,
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            {Ic.info(11)} blocking next level
          </span>
        )}
      </div>

      <div style={{ fontSize: 12, color: lgColors.textMid, lineHeight: 1.45 }}>{threat.detail}</div>

      {threat.affected.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {threat.affected.slice(0, 8).map((entry) => (
            <span
              key={entry}
              style={{
                fontSize: 11,
                fontFamily: F.mono,
                color: lgColors.textMid,
                background: "rgba(255,255,255,0.7)",
                border: "1px solid rgba(148,163,184,0.32)",
                borderRadius: 4,
                padding: "1px 6px",
              }}
            >
              {entry}
            </span>
          ))}
          {threat.affected.length > 8 && (
            <span style={{ fontSize: 11, color: lgColors.textMuted, fontFamily: F.mono }}>
              +{threat.affected.length - 8} more
            </span>
          )}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: 8,
          padding: "7px 10px",
          border: "1px solid rgba(34, 197, 94, 0.42)",
          background: "rgba(220, 252, 231, 0.6)",
          borderRadius: 8,
          fontSize: 12,
          color: lgColors.success,
        }}
      >
        <span style={{ display: "flex", flexShrink: 0 }}>{Ic.check(12)}</span>
        <span>{threat.remediation}</span>
      </div>
    </div>
  );
}

export function RepoAnalysisThreatsCard({
  hasReport,
  threats,
  loading,
}: {
  hasReport: boolean;
  threats: Threat[];
  loading: boolean;
}) {
  const sorted = threats; // backend already sorts blocking-first, then by severity

  return (
    <div style={lgContentCard()}>
      <CardHeader
        label="Reproducibility Threats"
        hint={
          !hasReport
            ? "Awaiting run"
            : loading
              ? "Loading…"
              : sorted.length > 0
                ? `${sorted.length} found`
                : "None detected"
        }
      />

      {!hasReport ? (
        <div
          style={{
            border: "1px dashed rgba(148, 163, 184, 0.5)",
            background: "rgba(255,255,255,0.45)",
            borderRadius: 9,
            padding: 16,
            textAlign: "center",
            color: lgColors.textMuted,
            fontSize: 12,
          }}
        >
          Run Evaluate to surface threats to reproducibility.
        </div>
      ) : sorted.length === 0 ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            border: "1px solid rgba(34, 197, 94, 0.42)",
            background: "rgba(220, 252, 231, 0.6)",
            borderRadius: 9,
            padding: 12,
            fontSize: 12,
            color: lgColors.success,
          }}
        >
          <span style={{ display: "flex" }}>{Ic.check(14)}</span>
          {loading ? "Loading report…" : "No reproducibility threats detected."}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {THREAT_DIMENSIONS.map(({ category, label }) => {
            const inDimension = sorted.filter((threat) => threat.category === category);
            if (inDimension.length === 0) return null;
            return (
              <div key={category} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                    color: lgColors.textMuted,
                    fontFamily: F.mono,
                  }}
                >
                  {label}
                </div>
                {inDimension.map((threat) => (
                  <ThreatRow key={threat.id} threat={threat} />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
