import { useEffect } from "react";
import { scanDependencies } from "../../../../../core/ree-assembly/assemblyDependencyAnalysis";
import { useApiRuntime } from "../../../../data/apiRuntime";
import { useEvaluateReportQuery } from "../../../../data/evaluate/queries";
import { Ic } from "../../../shared/components/Icon";
import {
  lgColors,
  lgNextButton,
  lgOutcomeBadge,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { assemblyStepIcon } from "../../assemblyStepIcons";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { PAGE } from "../../state/pages";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { countContainerAndNixFiles } from "./EvaluatePageHelpers";
import {
  EvaluateAxesCard,
  EvaluateDependenciesCard,
  EvaluateLogCard,
  EvaluateReadinessAside,
  EvaluateRunConsoleCard,
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
  ts,
  onRun,
  onCancel,
  onGo,
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
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={IC(24)}
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
            hasScoreOutput && ts ? (
              <span
                style={{
                  fontSize: 11,
                  color: lgColors.textMuted,
                  fontFamily: F.mono,
                  flexShrink: 0,
                }}
              >
                Last run{" "}
                {new Date(ts).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            ) : null
          }
        />

        <div style={lgStyles.mainGrid}>
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

              <EvaluateLogCard log={log} running={running} />
            </div>

            <div style={lgStyles.footer}>
              <span style={{ color: lgColors.textMuted, fontSize: 12 }}>
                {hasScoreOutput
                  ? "Evaluate output is current."
                  : "Run Evaluate to compute a reproducibility score."}
              </span>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button type="button" onClick={() => onGo?.(PAGE.BUILD)} style={lgNextButton()}>
                  Next: Runtime & SBOM {Ic.chevR(15)}
                </button>
              </div>
            </div>
          </section>

          <aside style={lgStyles.aside}>
            <EvaluateRunConsoleCard
              running={running}
              runDone={runDone}
              disabled={running || !sourceLoadedInWorkspace || hasMissing}
              sourceLoadedInWorkspace={sourceLoadedInWorkspace}
              missing={missing}
              onRun={() => onRun(assemblyStep.key, params)}
              onCancel={() => onCancel?.(assemblyStep.key)}
              onGoFields={onGoFields}
            />
            <EvaluateReadinessAside hasScoreOutput={hasScoreOutput} report={report} ts={ts} />
            <EvaluateWorkspaceAside
              sourceLoadedInWorkspace={sourceLoadedInWorkspace}
              containerCount={containerCount}
              nixCount={nixCount}
              manifestCount={depGroups.length}
              fileCount={files?.length ?? 0}
            />
          </aside>
        </div>
      </div>
    </div>
  );
}
