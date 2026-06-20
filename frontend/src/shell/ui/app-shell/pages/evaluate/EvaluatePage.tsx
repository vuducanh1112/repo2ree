import { scanDependencies } from "@core/ree-assembly/assemblyDependencyAnalysis";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useEvaluateReportQuery } from "@shell/data/evaluate/queries";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgColors, lgOutcomeBadge, lgStatusBadge, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import type React from "react";
import { useEffect } from "react";
import { assemblyStepIcon } from "../../assemblyStepIcons";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { countContainerAndNixFiles } from "./EvaluatePageHelpers";
import {
  EvaluateAxesCard,
  EvaluateDependenciesCard,
  EvaluateLogCard,
  EvaluateMissingInputs,
  EvaluateRunControls,
  EvaluateThreatsCard,
  EvaluateWorkspaceAside,
} from "./EvaluatePageSections";

export function PageEvaluate({
  assemblyStep,
  workspaceSourceState,
  workspaceFiles,
  log,
  running,
  runDone,
  badge,
  onRun,
  onCancel,
  onGoFields,
  missing,
  params,
}: AssemblyPageProps) {
  const files = workspaceFiles;
  const depGroups = scanDependencies(files || []);
  const { containerCount, nixCount } = countContainerAndNixFiles(files || []);
  const hasRun = !!log;
  const { reeId } = useApiRuntime();
  // The report is a persisted artifact, so fetch it whenever we have an REE — this
  // keeps the page populated across reloads/navigation (runDone is transient).
  const reportQuery = useEvaluateReportQuery({ reeId, enabled: !!reeId });
  const { refetch: refetchReport } = reportQuery;
  const report = reportQuery.data ?? null;
  const threats = report?.threats ?? [];
  // Refresh the report when a run finishes while the page is open.
  useEffect(() => {
    if (runDone) void refetchReport();
  }, [runDone, refetchReport]);
  const hasScoreOutput = !!report;
  const sourceLoadedInWorkspace = !!workspaceSourceState.sourceAvailable;
  const IC = assemblyStepIcon(assemblyStep.iconKey);
  const hasMissing = missing.length > 0;

  const statusLabel = running ? "Running" : hasScoreOutput ? "Scored" : "Not run";
  const statusReady = hasScoreOutput && !hasMissing;

  return (
    // Single column sitting directly on the focus dock — no right rail. The Run
    // action lives in the header; the evaluation result folds into the column.
    <div style={pageRoot}>
      <GlassPageHeader
        icon={IC(24)}
        iconTint={{
          color: "#7c3aed",
          border: "rgba(124, 58, 237, 0.32)",
          shadow: "rgba(124, 58, 237, 0.14)",
        }}
        title={assemblyStep.label}
        subtitle={assemblyStep.desc}
        badges={
          <>
            <span style={lgStatusBadge(statusReady)}>{statusLabel}</span>
            {hasScoreOutput && badge && (
              <span style={lgOutcomeBadge(badge.color, badge.bg)}>
                {Ic.check(11)} {badge.label}
              </span>
            )}
          </>
        }
        right={
          <EvaluateRunControls
            running={running}
            runDone={runDone}
            disabled={running || !sourceLoadedInWorkspace || hasMissing}
            onRun={() => onRun(assemblyStep.key, params)}
            onCancel={() => onCancel?.(assemblyStep.key)}
          />
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <EvaluateMissingInputs missing={missing} onGoFields={onGoFields} />

        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <div style={lgStyles.sectionHeader}>
              <div style={lgStyles.sectionIcon}>{Ic.layers(19)}</div>
              <div>
                <h2 style={lgStyles.sectionTitle}>Reproducibility Analysis</h2>
                <div style={lgStyles.sectionSubtitle}>
                  Dependency declaration and environment capture, scored as independent axes.
                </div>
              </div>
            </div>

            <EvaluateAxesCard hasScoreOutput={hasScoreOutput} report={report} />

            <EvaluateThreatsCard
              hasScoreOutput={hasScoreOutput}
              threats={threats}
              loading={reportQuery.isLoading}
            />

            <EvaluateDependenciesCard
              hasRun={hasRun}
              depGroups={depGroups}
              containerCount={containerCount}
              nixCount={nixCount}
            />
          </div>

          <div style={lgStyles.footer}>
            <span style={{ color: lgColors.textMuted, fontSize: 12 }}>
              {hasScoreOutput
                ? "Evaluate output is current."
                : "Run Evaluate to compute a reproducibility score."}
            </span>
          </div>
        </section>

        <EvaluateWorkspaceAside
          sourceLoadedInWorkspace={sourceLoadedInWorkspace}
          containerCount={containerCount}
          nixCount={nixCount}
          manifestCount={depGroups.length}
          fileCount={files?.length ?? 0}
        />

        <EvaluateLogCard log={log} running={running} />
      </div>
    </div>
  );
}

// Transparent page so the dock surface reads through; generous top padding
// clears the dock's stage label and close button.
const pageRoot: React.CSSProperties = {
  height: "100%",
  minHeight: 0,
  overflow: "auto",
  padding: "46px 36px 32px",
  color: lgColors.text,
};
