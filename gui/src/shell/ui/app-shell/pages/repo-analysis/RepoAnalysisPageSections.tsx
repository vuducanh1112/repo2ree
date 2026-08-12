import { DEPENDENCY_AXIS, ENVIRONMENT_AXIS, MACHINE_AXIS } from "@core/evaluate/axes";
import type { DependencyGroup } from "@core/evaluate/dependencyPresentation";
import type { ReproducibilityReport } from "@core/evaluate/Threat";
import type { LogEntry } from "@core/ree/ReeTypes";
import type { ReeStepRequirement } from "@core/ree-steps/stepTypes";
import { GlassPanel } from "@shell/ui/app-shell/components/GlassPageShell";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { Surface } from "@shell/ui/shared/components/Surface";
import { axisTone } from "@shell/ui/theme/appearance";
import { cssVars } from "@shell/ui/theme/styleVars";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { MissingInputsBanner } from "../../components/MissingInputsBanner";
import { RunActionButton } from "../../components/RunActionButton";
import { SummaryLine } from "../../components/SummaryLine";
import { DependencyPanel } from "../../components/stepRunPanels/DependencyPanel";
import { CardHeader } from "./RepoAnalysisCardHeader";
import styles from "./RepoAnalysisPage.module.css";
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
    <div style={cssVars({ "--axis-tint": accent })}>
      <div className={styles.axisHead}>
        <span className={styles.axisLabel}>{label}</span>
        <span className={styles.axisLevel}>{hint}</span>
      </div>
      <div className={styles.axisTrack}>
        {stepLabels.map((stepLabel, idx) => {
          const reached = idx <= level;
          const isActive = idx === level;
          return (
            <div key={stepLabel} className={styles.axisStepWrap}>
              <div
                className={styles.axisStep}
                data-reached={reached || undefined}
                data-current={isActive || undefined}
              >
                {stepLabel}
              </div>
              {idx < stepLabels.length - 1 && (
                <div className={styles.axisLink} data-reached={reached || undefined} />
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
    <Surface>
      <CardHeader
        label="Repository Axes"
        hint={hasReport ? "Three independent axes" : "Awaiting run"}
      />

      {hasReport && report ? (
        <div className={styles.axes}>
          <AxisTrack
            label="Dependency declaration"
            hint={report.dependencyLevelLabel}
            stepLabels={DEPENDENCY_AXIS.steps}
            level={report.dependencyLevel}
            accent={axisTone(DEPENDENCY_AXIS.key)}
          />
          <AxisTrack
            label="Environment capture"
            hint={report.environmentLevelLabel}
            stepLabels={ENVIRONMENT_AXIS.steps}
            level={report.environmentLevel}
            accent={axisTone(ENVIRONMENT_AXIS.key)}
          />
          <AxisTrack
            label="Machine capture"
            hint={report.machineLevelLabel}
            stepLabels={MACHINE_AXIS.steps}
            level={report.machineLevel}
            accent={axisTone(MACHINE_AXIS.key)}
          />
        </div>
      ) : (
        <div className={styles.placeholder}>
          No Evaluate output yet. Run the evaluator to analyze the repository&apos;s dependency,
          environment, and machine axes.
        </div>
      )}
    </Surface>
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
    <Surface>
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
            <div className={styles.placeholder} data-emphasis="strong">
              <div aria-hidden className={styles.placeholderIcon}>
                {Ic.package(20)}
              </div>
              <div>No manifest files found</div>
              <div className={styles.placeholderHint}>
                Add requirements.txt, pyproject.toml, environment.yml, or package.json.
              </div>
            </div>
          )}

          <div className={styles.counts}>
            <Badge tone={containerCount > 0 ? "success" : "warning"}>
              Container files: {containerCount}
            </Badge>
            <Badge tone={nixCount > 0 ? "success" : "warning"}>Nix files: {nixCount}</Badge>
          </div>
        </>
      ) : (
        <div className={styles.manifests}>
          {EXPECTED_DEP_FILES.map((item) => (
            <div key={item.label} className={styles.manifest} data-kind={item.kind}>
              <span aria-hidden className={styles.manifestIcon}>
                {Ic.file(12)}
              </span>
              <span className={styles.manifestName}>{item.label}</span>
              <span className={styles.manifestHint}>{item.hint}</span>
            </div>
          ))}
        </div>
      )}
    </Surface>
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
    <GlassPanel density="compact">
      <div className={styles.asideHead}>
        <span aria-hidden className={styles.asideIcon}>
          {Ic.package(22)}
        </span>
        <h2 className={styles.asideTitle}>Workspace Inputs</h2>
      </div>

      <Surface spacing="flush">
        <div className={styles.readout}>
          <SummaryLine
            label="Source"
            value={
              <Badge tone={sourceLoadedInWorkspace ? "success" : "warning"}>
                {sourceLoadedInWorkspace ? "Loaded" : "Not loaded"}
              </Badge>
            }
          />
          <SummaryLine label="Files scanned" value={fileCount.toString()} />
          <SummaryLine label="Manifest groups" value={manifestCount.toString()} />
          <SummaryLine label="Container files" value={containerCount.toString()} />
          <SummaryLine label="Nix files" value={nixCount.toString()} />
        </div>
      </Surface>
    </GlassPanel>
  );
}
