import type { LogEntry } from "../../../../../core/ree/ReeTypes";
import type { DepGroup } from "../../../../../core/ree-assembly/assemblyDependencyAnalysis";
import type { ReeAssemblyRequirement } from "../../../../../core/ree-assembly/assemblyStepTypes";
import { LEVELS } from "../../../../../core/review/levels";
import { Ic } from "../../../shared/components/Icon";
import { LevelBadge } from "../../../shared/components/LevelBadge";
import {
  lgColors,
  lgContentCard,
  lgReadout,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
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

export function EvaluateRunConsoleCard({
  running,
  runDone,
  disabled,
  sourceLoadedInWorkspace,
  missing,
  onRun,
  onCancel,
  onGoFields,
}: {
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  sourceLoadedInWorkspace: boolean;
  missing: ReeAssemblyRequirement[];
  onRun: () => void;
  onCancel: () => void;
  onGoFields?: () => void;
}) {
  const hasMissing = missing.length > 0;
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
  };

  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.play(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Run Evaluate</h2>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {hasMissing && (
          <div
            style={{
              border: `1px solid ${lgColors.dangerBorder}`,
              background: "rgba(255, 241, 242, 0.7)",
              borderRadius: 8,
              padding: 10,
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
        )}
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          style={{ ...runStyle, width: "100%", justifyContent: "center" }}
        >
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
              width: "100%",
            }}
          >
            {Ic.x(14)} Cancel
          </button>
        )}
        {!hasMissing && (
          <span style={lgStyles.helper}>
            {sourceLoadedInWorkspace
              ? "Scans the workspace and computes a reproducibility level."
              : "Load source into the workspace first."}
          </span>
        )}
      </div>
    </section>
  );
}

export function EvaluateReproducibilityCard({
  hasScoreOutput,
  level,
}: {
  hasScoreOutput: boolean;
  level: number;
}) {
  const active = LEVELS[level];

  return (
    <div style={lgContentCard()}>
      <CardHeader
        label="Reproducibility Ladder"
        hint={hasScoreOutput ? `Standing L${level} of ${LEVELS.length - 1}` : "Awaiting run"}
      />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 14,
          flexWrap: "wrap",
        }}
      >
        {LEVELS.map((levelConfig, idx) => {
          const reached = hasScoreOutput && idx <= level;
          const isActive = hasScoreOutput && idx === level;
          return (
            <div key={levelConfig.n} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div
                title={levelConfig.label}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: 30,
                  height: 26,
                  padding: "0 8px",
                  borderRadius: 99,
                  fontSize: 11,
                  fontWeight: 800,
                  fontFamily: F.mono,
                  color: reached ? levelConfig.ink : lgColors.textMuted,
                  background: reached ? levelConfig.bg : "rgba(255,255,255,0.6)",
                  border: `1px solid ${
                    isActive
                      ? `${levelConfig.color}aa`
                      : reached
                        ? `${levelConfig.color}55`
                        : "rgba(148,163,184,0.32)"
                  }`,
                  boxShadow: isActive ? `0 0 0 3px ${levelConfig.color}22` : "none",
                }}
              >
                L{levelConfig.n}
              </div>
              {idx < LEVELS.length - 1 && (
                <div
                  style={{
                    width: 18,
                    height: 2,
                    borderRadius: 99,
                    background: reached ? `${levelConfig.color}88` : "rgba(148,163,184,0.28)",
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {hasScoreOutput ? (
        <div
          style={{
            border: `1px solid ${active.color}44`,
            background: active.bg,
            borderRadius: 9,
            padding: 12,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <LevelBadge level={level} />
            <span style={{ fontSize: 13, fontWeight: 700, color: active.ink }}>{active.label}</span>
          </div>
          <div style={{ fontSize: 12, color: lgColors.textMid, lineHeight: 1.45 }}>
            {active.desc}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div
              style={{
                display: "flex",
                gap: 8,
                padding: "8px 10px",
                border: "1px solid rgba(245, 158, 11, 0.42)",
                background: "rgba(254, 252, 232, 0.82)",
                borderRadius: 8,
                fontSize: 12,
                color: lgColors.warning,
              }}
            >
              <span style={{ display: "flex", flexShrink: 0 }}>{Ic.info(12)}</span>
              <span>{active.problem || "No bottleneck called out at this level."}</span>
            </div>
            <div
              style={{
                display: "flex",
                gap: 8,
                padding: "8px 10px",
                border: "1px solid rgba(34, 197, 94, 0.42)",
                background: "rgba(220, 252, 231, 0.78)",
                borderRadius: 8,
                fontSize: 12,
                color: lgColors.success,
              }}
            >
              <span style={{ display: "flex", flexShrink: 0 }}>{Ic.check(12)}</span>
              <span>{active.fix || "No additional fix suggested at this level."}</span>
            </div>
          </div>
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
          No Evaluate output yet. Run the evaluator to place this REE on the ladder.
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

export function EvaluateReadinessAside({
  hasScoreOutput,
  level,
  completionPct,
  ts,
}: {
  hasScoreOutput: boolean;
  level: number;
  completionPct: number;
  ts?: string | null;
}) {
  const active = LEVELS[level];
  const standing = `${level} / ${LEVELS.length - 1}`;

  return (
    <section style={{ ...lgStyles.panel, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.shield(22)}</span>
        <h2 style={{ margin: 0, fontSize: 15, color: lgColors.text }}>Evaluation Result</h2>
      </div>

      <div style={lgStyles.summaryBox}>
        <div style={lgStyles.overviewHeader}>
          <span style={lgStyles.overviewLabel}>Standing</span>
          <span style={lgStatusBadge(hasScoreOutput)}>{hasScoreOutput ? "Scored" : "Not run"}</span>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "10px 0",
          }}
        >
          {hasScoreOutput ? (
            <LevelBadge level={level} large />
          ) : (
            <div style={{ fontSize: 12, color: lgColors.textMuted, fontStyle: "italic" }}>
              Run Evaluate to place on ladder
            </div>
          )}
        </div>
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 11,
              color: lgColors.textMuted,
              marginBottom: 4,
            }}
          >
            <span>Progress</span>
            <span style={{ color: lgColors.blue, fontFamily: F.mono }}>{completionPct}%</span>
          </div>
          <div style={lgStyles.progressTrack}>
            <div
              style={{
                ...lgStyles.progressFill,
                width: `${hasScoreOutput ? completionPct : 0}%`,
                background: hasScoreOutput
                  ? `linear-gradient(90deg, ${active.color}, ${lgColors.indigo})`
                  : lgStyles.progressFill.background,
              }}
            />
          </div>
        </div>
        <div style={lgStyles.statGrid}>
          <div style={lgReadout(lgStyles.statReadout)}>
            <span style={{ color: lgColors.textMuted, fontSize: 11 }}>Standing</span>
            <strong style={{ color: lgColors.text, fontSize: 18, fontFamily: F.mono }}>
              {hasScoreOutput ? standing : "—"}
            </strong>
          </div>
          <div style={lgReadout(lgStyles.statReadout)}>
            <span style={{ color: lgColors.textMuted, fontSize: 11 }}>Last run</span>
            <strong style={{ color: lgColors.text, fontSize: 13, fontFamily: F.mono }}>
              {hasScoreOutput && ts
                ? new Date(ts).toLocaleString([], {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "Never"}
            </strong>
          </div>
        </div>
      </div>
    </section>
  );
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
