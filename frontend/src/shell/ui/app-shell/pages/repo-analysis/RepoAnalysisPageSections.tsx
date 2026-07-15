import { DEPENDENCY_AXIS, ENVIRONMENT_AXIS, MACHINE_AXIS } from "@core/evaluate/axes";
import type { DependencyGroup } from "@core/evaluate/dependencyPresentation";
import type { ReproducibilityReport } from "@core/evaluate/Threat";
import type { LogEntry } from "@core/ree/ReeTypes";
import type { ReeStepRequirement } from "@core/ree-steps/stepTypes";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgContentCard, lgStatusBadge, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { RunActionButton } from "../../components/RunActionButton";
import { SummaryLine } from "../../components/SummaryLine";
import { DependencyPanel } from "../../components/stepRunPanels/DependencyPanel";
import { CardHeader } from "./RepoAnalysisCardHeader";
import { EXPECTED_DEP_FILES } from "./RepoAnalysisPageHelpers";

// RepoAnalysisThreatsCard lives in its own module; re-exported so the page keeps a
// single import surface.
export { RepoAnalysisThreatsCard } from "./RepoAnalysisThreatsCard";

// Run / Re-run (+ Cancel while running) — lives in the page header's action
// slot, mirroring the other pages.
export function RepoAnalysisRunControls({
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
  return (
    <RunActionButton
      label={running ? "Running…" : runDone ? "Re-run Evaluate" : "Run Evaluate"}
      running={running}
      disabled={disabled}
      onRun={onRun}
      onCancel={onCancel}
    />
  );
}

// Surfaced inline in the column (the rail that used to host it is gone) so a
// missing prerequisite still blocks the run with a clear way back.
export function RepoAnalysisMissingInputs({
  missing,
  onGoFields,
}: {
  missing: ReeStepRequirement[];
  onGoFields?: () => void;
}) {
  return (
    <MissingInputsBanner missing={missing} onGoFields={onGoFields} goLabel="← Source Acquisition" />
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

export function RepoAnalysisAxesCard({
  hasReport,
  report,
}: {
  hasReport: boolean;
  report: ReproducibilityReport | null;
}) {
  return (
    <div style={lgContentCard()}>
      <CardHeader
        label="Repository Axes"
        hint={hasReport ? "Three independent axes" : "Awaiting run"}
      />

      {hasReport && report ? (
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
          No Evaluate output yet. Run the evaluator to analyze the repository&apos;s dependency,
          environment, and machine axes.
        </div>
      )}
    </div>
  );
}

export function RepoAnalysisDependenciesCard({
  hasRun,
  depGroups,
  containerCount,
  nixCount,
}: {
  hasRun: boolean;
  depGroups: DependencyGroup[];
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

export function RepoAnalysisLogCard({ log, running }: { log: LogEntry | null; running: boolean }) {
  return <CollapsibleLogCard log={log} running={running} title="Run Log" maxHeight={280} />;
}

export function RepoAnalysisWorkspaceAside({
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
