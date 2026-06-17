import type { LogEntry } from "../../../../../core/ree/ReeTypes";
import type { DepGroup } from "../../../../../core/ree-assembly/assemblyDependencyAnalysis";
import type { ReeAssemblyRequirement } from "../../../../../core/ree-assembly/assemblyStepTypes";
import { DEPENDENCY_AXIS, ENVIRONMENT_AXIS, MACHINE_AXIS } from "../../../../../core/review/axes";
import type {
  ReproducibilityReport,
  Threat,
  ThreatCategory,
  ThreatSeverity,
} from "../../../../../core/review/Threat";
import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgContentCard, lgStatusBadge, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { DependencyPanel } from "../../components/assemblyRunPanels";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { SummaryLine } from "../../components/SummaryLine";
import { EXPECTED_DEP_FILES } from "./EvaluatePageHelpers";

function CardHeader({ label, hint }: { label: string; hint?: string }) {
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

// Run / Re-run (+ Cancel while running) — lives in the page header's action
// slot now that the right rail is gone, mirroring the other redesigned pages.
export function EvaluateRunControls({
  running,
  runDone,
  disabled,
  onRun,
  onCancel,
}: {
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  onRun: () => void;
  onCancel: () => void;
}) {
  const buttonLabel = running ? "Running…" : runDone ? "Re-run Evaluate" : "Run Evaluate";

  const runStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    border: `1px solid ${disabled ? "rgba(148,163,184,0.34)" : "rgba(14, 165, 233, 0.42)"}`,
    background: disabled
      ? "rgba(241, 245, 249, 0.72)"
      : `linear-gradient(135deg, ${lgColors.blue}, ${lgColors.indigo})`,
    color: disabled ? lgColors.textMuted : lgColors.white,
    padding: "10px 18px",
    borderRadius: 8,
    fontWeight: 800,
    fontFamily: F.sans,
    cursor: disabled ? "not-allowed" : "pointer",
    boxShadow: disabled ? "none" : "0 14px 30px rgba(14, 165, 233, 0.22)",
    flexShrink: 0,
  };

  return (
    <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
      <button type="button" onClick={onRun} disabled={disabled} style={runStyle}>
        <span
          style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
        >
          {running ? Ic.loader(14) : Ic.play(14)}
        </span>
        {buttonLabel}
      </button>
      {running && (
        <button
          type="button"
          onClick={onCancel}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            border: `1px solid ${lgColors.dangerBorder}`,
            background: "rgba(255, 241, 242, 0.82)",
            color: lgColors.danger,
            padding: "8px 14px",
            borderRadius: 8,
            fontWeight: 700,
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          {Ic.x(14)} Cancel
        </button>
      )}
    </div>
  );
}

// Surfaced inline in the column (the rail that used to host it is gone) so a
// missing prerequisite still blocks the run with a clear way back.
export function EvaluateMissingInputs({
  missing,
  onGoFields,
}: {
  missing: ReeAssemblyRequirement[];
  onGoFields?: () => void;
}) {
  if (missing.length === 0) return null;
  return (
    <div
      style={{
        border: `1px solid ${lgColors.dangerBorder}`,
        background: "rgba(255, 241, 242, 0.7)",
        borderRadius: 9,
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
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
          ← Source Acquisition
        </button>
      )}
    </div>
  );
}

function AxisTrack({
  label,
  hint,
  stepLabels,
  level,
  accent,
}: {
  label: string;
  hint: string;
  stepLabels: readonly string[];
  level: number;
  accent: string;
}) {
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 800, color: lgColors.text }}>{label}</span>
        <span style={{ fontSize: 11, color: accent, fontFamily: F.mono, fontWeight: 700 }}>
          {hint}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        {stepLabels.map((stepLabel, idx) => {
          const reached = idx <= level;
          const isActive = idx === level;
          return (
            <div key={stepLabel} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  height: 24,
                  padding: "0 10px",
                  borderRadius: 99,
                  fontSize: 11,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  color: reached ? accent : lgColors.textMuted,
                  background: reached ? `${accent}14` : "rgba(255,255,255,0.6)",
                  border: `1px solid ${
                    isActive ? `${accent}aa` : reached ? `${accent}55` : "rgba(148,163,184,0.32)"
                  }`,
                  boxShadow: isActive ? `0 0 0 3px ${accent}22` : "none",
                }}
              >
                {stepLabel}
              </div>
              {idx < stepLabels.length - 1 && (
                <div
                  style={{
                    width: 14,
                    height: 2,
                    borderRadius: 99,
                    background: reached ? `${accent}88` : "rgba(148,163,184,0.28)",
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function EvaluateAxesCard({
  hasScoreOutput,
  report,
}: {
  hasScoreOutput: boolean;
  report: ReproducibilityReport | null;
}) {
  return (
    <div style={lgContentCard()}>
      <CardHeader
        label="Reproducibility Axes"
        hint={hasScoreOutput ? "Two independent dimensions" : "Awaiting run"}
      />

      {hasScoreOutput && report ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <AxisTrack
            label="Dependency declaration"
            hint={report.dependencyLevelLabel}
            stepLabels={DEPENDENCY_AXIS.steps}
            level={report.dependencyLevel}
            accent={lgColors.blue}
          />
          <AxisTrack
            label="Environment capture"
            hint={report.environmentLevelLabel}
            stepLabels={ENVIRONMENT_AXIS.steps}
            level={report.environmentLevel}
            accent={lgColors.cyan}
          />
          <AxisTrack
            label="Machine capture"
            hint={report.machineLevelLabel}
            stepLabels={MACHINE_AXIS.steps}
            level={report.machineLevel}
            accent={lgColors.indigo}
          />
        </div>
      ) : (
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
          No Evaluate output yet. Run the evaluator to score the dependency and environment axes.
        </div>
      )}
    </div>
  );
}

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

export function EvaluateThreatsCard({
  hasScoreOutput,
  threats,
  loading,
}: {
  hasScoreOutput: boolean;
  threats: Threat[];
  loading: boolean;
}) {
  const sorted = threats; // backend already sorts blocking-first, then by severity

  return (
    <div style={lgContentCard()}>
      <CardHeader
        label="Reproducibility Threats"
        hint={
          !hasScoreOutput
            ? "Awaiting run"
            : loading
              ? "Loading…"
              : sorted.length > 0
                ? `${sorted.length} found`
                : "None detected"
        }
      />

      {!hasScoreOutput ? (
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

export function EvaluateDependenciesCard({
  hasRun,
  depGroups,
  containerCount,
  nixCount,
}: {
  hasRun: boolean;
  depGroups: DepGroup[];
  containerCount: number;
  nixCount: number;
}) {
  return (
    <div style={lgContentCard()}>
      <CardHeader
        label="Detected Dependencies"
        hint={
          hasRun
            ? `${depGroups.length} manifest group${depGroups.length === 1 ? "" : "s"}`
            : "Run to scan"
        }
      />

      {hasRun ? (
        <>
          {depGroups.length > 0 ? (
            <DependencyPanel depGroups={depGroups} />
          ) : (
            <div
              style={{
                border: "1.5px dashed rgba(148, 163, 184, 0.55)",
                borderRadius: 9,
                padding: 16,
                textAlign: "center",
                color: lgColors.textMuted,
              }}
            >
              <div
                style={{ display: "flex", justifyContent: "center", marginBottom: 6, opacity: 0.5 }}
              >
                {Ic.package(20)}
              </div>
              <div style={{ fontSize: 12 }}>No manifest files found</div>
              <div style={{ fontSize: 11, marginTop: 3 }}>
                Add requirements.txt, pyproject.toml, environment.yml, or package.json.
              </div>
            </div>
          )}

          <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span style={lgStatusBadge(containerCount > 0)}>Container files: {containerCount}</span>
            <span style={lgStatusBadge(nixCount > 0)}>Nix files: {nixCount}</span>
          </div>
        </>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {EXPECTED_DEP_FILES.map((item) => (
            <div
              key={item.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "7px 10px",
                border: `1px dashed ${item.color}40`,
                borderRadius: 8,
                background: "rgba(255,255,255,0.45)",
              }}
            >
              <span style={{ display: "flex", color: item.color, opacity: 0.7 }}>
                {Ic.file(12)}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: item.color,
                  fontWeight: 700,
                  flex: 1,
                }}
              >
                {item.label}
              </span>
              <span style={{ fontSize: 10, color: lgColors.textMuted }}>{item.hint}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EvaluateLogCard({ log, running }: { log: LogEntry | null; running: boolean }) {
  return <CollapsibleLogCard log={log} running={running} title="Run Log" maxHeight={280} />;
}

export function EvaluateWorkspaceAside({
  sourceLoadedInWorkspace,
  containerCount,
  nixCount,
  manifestCount,
  fileCount,
}: {
  sourceLoadedInWorkspace: boolean;
  containerCount: number;
  nixCount: number;
  manifestCount: number;
  fileCount: number;
}) {
  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.package(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Workspace Inputs</h2>
      </div>

      <div style={lgStyles.summaryBox}>
        <SummaryLine
          label="Source"
          value={
            <span style={lgStatusBadge(sourceLoadedInWorkspace)}>
              {sourceLoadedInWorkspace ? "Loaded" : "Not loaded"}
            </span>
          }
        />
        <SummaryLine label="Files scanned" value={fileCount.toString()} />
        <SummaryLine label="Manifest groups" value={manifestCount.toString()} />
        <SummaryLine label="Container files" value={containerCount.toString()} />
        <SummaryLine label="Nix files" value={nixCount.toString()} />
      </div>
    </section>
  );
}
