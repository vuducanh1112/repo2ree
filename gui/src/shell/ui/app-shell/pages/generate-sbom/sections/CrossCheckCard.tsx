import { latestCrossCheckSummary } from "@core/evaluate/crossCheckRun";
import type { SbomCrossCheckSummary } from "@core/evaluate/Threat";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useEvaluateReportQuery } from "@shell/data/evaluate/queries";
import { useStartReeRunMutation } from "@shell/data/runs/mutations";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Surface } from "@shell/ui/shared/components/Surface";
import { RunActionButton } from "../../../components/RunActionButton";
import styles from "../GenerateSbomPage.module.css";

/**
 * Cross-check the runtime SBOM against the scanned dependency inventory.
 * A lightweight run (no step-catalog node): results land in the evaluate
 * report and aggregate audit. The
 * per-dependency presence badges render in the readiness page's inventory
 * table; this card owns the trigger and the aggregates.
 */
export function CrossCheckCard({ sbomReady, color }: { sbomReady: boolean; color: string }) {
  const { reeId } = useApiRuntime();
  const reportQuery = useEvaluateReportQuery({ reeId, enabled: !!reeId });
  const runsQuery = useReeRunsQuery();
  const startRun = useStartReeRunMutation();
  const runs = runsQuery.data ?? [];
  const checking =
    startRun.isPending ||
    runs.some((run) => run.operation === "crosscheck" && !isTerminalReeRunStatus(run.status));
  const hasReport = !!reportQuery.data;
  // The cross-check does not land in the evaluate report: that artifact is the
  // evaluate run's own evidence, digest-pinned by its receipt, so a later run
  // may not rewrite it. The result rides on the cross-check run instead —
  // aggregates and the undeclared packages both — and the run list is already
  // in hand here, so read the newest succeeded one.
  const summary = latestCrossCheckSummary(runs);
  const disabled = checking || !sbomReady || !hasReport;

  return (
    <Surface spacing="flush">
      <div className={styles.crossCheck}>
        <div className={styles.crossCheckHead}>
          <span className={styles.crossCheckKind}>Runtime cross-check</span>
          <Badge tone={summary ? "success" : "warning"}>
            {summary ? "Cross-checked" : "Not cross-checked"}
          </Badge>
          <div className={styles.spacer} />
          <RunActionButton
            label={checking ? "Checking…" : summary ? "Re-check" : "Cross-check"}
            running={checking}
            disabled={disabled}
            iconSize={13}
            variant="accent"
            tint={color}
            onRun={() => startRun.mutate({ scriptKey: "crosscheck" })}
          />
        </div>

        <div className={styles.crossCheckHint}>
          Which declared dependencies actually made it into the built runtime — the SBOM joined
          against the scanned inventory. Per-dependency verdicts appear in the readiness page's
          dependency table.
        </div>

        {!hasReport && sbomReady && (
          <span className={styles.crossCheckNote}>
            Run Evaluate first — the cross-check compares the SBOM against the scanned dependency
            inventory.
          </span>
        )}

        {summary && <CrossCheckResults summary={summary} />}
      </div>
    </Surface>
  );
}

/**
 * Aggregates of the cross-check. "Not in runtime" is evidence, not a defect —
 * dev/build-only deps legitimately never reach the runtime — so only the
 * undeclared packages get an itemized list.
 */
function CrossCheckResults({ summary }: { summary: SbomCrossCheckSummary }) {
  return (
    <div className={styles.results}>
      <div className={styles.aggregates}>
        <Badge
          tone={summary.observedMatched === summary.declaredDirectTotal ? "success" : "warning"}
        >
          {summary.observedMatched}/{summary.declaredDirectTotal} declared deps in runtime
        </Badge>
        <Badge tone={summary.versionMismatches === 0 ? "success" : "warning"}>
          Version mismatches: {summary.versionMismatches}
        </Badge>
        <Badge tone={summary.undeclaredSameEcosystem === 0 ? "success" : "warning"}>
          Undeclared in runtime: {summary.undeclaredSameEcosystem}
        </Badge>
        <span className={styles.crossCheckNote}>
          {summary.observedTotal} packages observed in total
        </span>
      </div>
      {summary.undeclared.length > 0 && (
        <div className={styles.undeclared}>
          {summary.undeclared.map((pkg) => (
            <span key={`${pkg.ecosystem}:${pkg.name}`} className={styles.undeclaredPkg}>
              {pkg.name}
              {pkg.version ? `@${pkg.version}` : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
