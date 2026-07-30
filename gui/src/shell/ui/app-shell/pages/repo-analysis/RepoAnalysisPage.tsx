import { groupEvaluatedDependencies } from "@core/evaluate/dependencyPresentation";
import { countEnvironmentFiles } from "@core/workspace/environmentFiles";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useEvaluateReportQuery } from "@shell/data/evaluate/queries";
import { Ic } from "@shell/ui/shared/components/Icon";
import { lgPageRoot, lgStatusBadge, lgStyles, pageIconTint } from "@shell/ui/theme/lightGlassTheme";
import { useEffect, useMemo } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { OutcomeBadge } from "../../components/OutcomeBadge";
import { stepIcon } from "../../stepIcons";
import type { StepPageProps } from "../sharedStepUi";
import {
  RepoAnalysisAxesCard,
  RepoAnalysisDependenciesCard,
  RepoAnalysisLogCard,
  RepoAnalysisMissingInputs,
  RepoAnalysisRunControls,
  RepoAnalysisThreatsCard,
  RepoAnalysisWorkspaceAside,
} from "./RepoAnalysisPageSections";

export function PageRepoAnalysis({
  step,
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
}: StepPageProps) {
  const files = workspaceFiles;
  const { containerCount, nixCount } = countEnvironmentFiles(files || []);
  const { reeId } = useApiRuntime();
  // The report is a persisted artifact, so fetch it whenever we have an REE — this
  // keeps the page populated across reloads/navigation (runDone is transient).
  const reportQuery = useEvaluateReportQuery({ reeId, enabled: !!reeId });
  const { refetch: refetchReport } = reportQuery;
  const report = reportQuery.data ?? null;
  // The closure can be large (full lockfile contents); group once per report.
  const depGroups = useMemo(() => groupEvaluatedDependencies(report?.dependencies ?? []), [report]);
  const threats = report?.threats ?? [];
  // Refresh on each terminal transition. `runDone` stays true after the first
  // successful run, so watching it alone leaves a re-run showing the old
  // persisted report.
  useEffect(() => {
    if (!running && runDone) void refetchReport();
  }, [running, runDone, refetchReport]);
  const hasReport = !!report;
  const sourceLoadedInWorkspace = !!workspaceSourceState.sourceAvailable;
  const IC = stepIcon(step.iconKey);
  const hasMissing = missing.length > 0;

  const statusLabel = running ? "Running" : hasReport ? "Analyzed" : "Not run";
  const statusReady = hasReport && !hasMissing;

  return (
    // Single column sitting directly on the focus dock — no right rail. The Run
    // action lives in the header; the evaluation result folds into the column.
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={IC(24)}
        iconTint={pageIconTint("#7c3aed")}
        title={step.label}
        subtitle={step.desc}
        badges={
          <>
            <span style={lgStatusBadge(statusReady)}>{statusLabel}</span>
            {hasReport && badge && <OutcomeBadge badge={badge} />}
          </>
        }
        right={
          <RepoAnalysisRunControls
            running={running}
            runDone={runDone}
            disabled={running || !sourceLoadedInWorkspace || hasMissing}
            onRun={() => onRun(step.key, params)}
            onCancel={() => onCancel?.(step.key)}
          />
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <RepoAnalysisMissingInputs missing={missing} onGoFields={onGoFields} />

        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <div style={lgStyles.sectionHeader}>
              <div style={lgStyles.sectionIcon}>{Ic.layers(19)}</div>
              <div>
                <h2 style={lgStyles.sectionTitle}>Source Repository Analysis</h2>
                <div style={lgStyles.sectionSubtitle}>
                  What the repository gives anyone who clones it: dependency declaration,
                  environment capture, and machine capture as independent axes.
                </div>
              </div>
            </div>

            <RepoAnalysisAxesCard hasReport={hasReport} report={report} />

            <RepoAnalysisThreatsCard
              hasReport={hasReport}
              threats={threats}
              loading={reportQuery.isLoading}
            />

            <RepoAnalysisDependenciesCard
              hasRun={hasReport}
              depGroups={depGroups}
              containerCount={containerCount}
              nixCount={nixCount}
            />
          </div>

          <GlassPanelFooter>
            {hasReport
              ? "Evaluate output is current."
              : "Run Evaluate to analyze the source repository."}
          </GlassPanelFooter>
        </section>

        <RepoAnalysisWorkspaceAside
          sourceLoadedInWorkspace={sourceLoadedInWorkspace}
          containerCount={containerCount}
          nixCount={nixCount}
          manifestCount={depGroups.length}
          fileCount={files?.length ?? 0}
        />

        <RepoAnalysisLogCard log={log} running={running} />
      </div>
    </div>
  );
}
