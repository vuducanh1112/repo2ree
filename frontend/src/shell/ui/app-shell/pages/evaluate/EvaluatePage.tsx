import { scanDependencies } from "../../../../../core/ree-assembly/assemblyDependencyAnalysis";
import { LEVELS } from "../../../../../core/review/levels";
import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgNextButton, lgStatusBadge, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { assemblyStepIcon } from "../../assemblyStepIcons";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { PAGE } from "../../state/pages";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { countContainerAndNixFiles } from "./EvaluatePageHelpers";
import {
  EvaluateDependenciesCard,
  EvaluateLogCard,
  EvaluateReadinessAside,
  EvaluateReproducibilityCard,
  EvaluateRunConsoleCard,
  EvaluateWorkspaceAside,
} from "./EvaluatePageSections";

export function PageEvaluate({
  assemblyStep,
  workspaceSourceState,
  evaluationState,
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
  const hasScoreOutput = !!runDone;
  const sourceLoadedInWorkspace = !!workspaceSourceState.sourceAvailable;
  const IC = assemblyStepIcon(assemblyStep.iconKey);
  const level = Math.min(evaluationState.evalLevel ?? 0, LEVELS.length - 1);
  const completionPct = Math.round((level / (LEVELS.length - 1)) * 100);
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
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: badge.color,
                    background: badge.bg,
                    border: `1px solid ${badge.color}40`,
                    borderRadius: 99,
                    padding: "3px 9px",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
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
                    Declared dependencies, container and Nix signals, and the resulting level.
                  </div>
                </div>
              </div>

              <EvaluateReproducibilityCard hasScoreOutput={hasScoreOutput} level={level} />

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
                  Next: Build Runtime {Ic.chevR(15)}
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
            <EvaluateReadinessAside
              hasScoreOutput={hasScoreOutput}
              level={level}
              completionPct={completionPct}
              ts={ts}
            />
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
