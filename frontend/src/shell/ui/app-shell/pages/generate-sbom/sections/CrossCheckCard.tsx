import type { SbomCrossCheckSummary } from "@core/evaluate/Threat";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useEvaluateReportQuery } from "@shell/data/evaluate/queries";
import { useStartReeRunMutation } from "@shell/data/runs/mutations";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import {
  lgAccentActionButton,
  lgColors,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { RunActionButton } from "../../../components/RunActionButton";

/**
 * Cross-check the runtime SBOM against the scanned dependency inventory.
 * A lightweight run (no step-catalog node): results land in the evaluate
 * report and the scorecard, both refreshed by the run-terminal sync. The
 * per-dependency presence badges render in the readiness page's inventory
 * table; this card owns the trigger and the aggregates.
 */
export function CrossCheckCard({ sbomReady, color }: { sbomReady: boolean; color: string }) {
  const { reeId } = useApiRuntime();
  const reportQuery = useEvaluateReportQuery({ reeId, enabled: !!reeId });
  const runsQuery = useReeRunsQuery();
  const startRun = useStartReeRunMutation();
  const checking =
    startRun.isPending ||
    (runsQuery.data ?? []).some(
      (run) => run.operation === "crosscheck" && !isTerminalReeRunStatus(run.status),
    );
  const hasReport = !!reportQuery.data;
  const summary = reportQuery.data?.sbomCrossCheck ?? null;
  const disabled = checking || !sbomReady || !hasReport;

  return (
    <div
      style={{ ...lgStyles.summaryBox, flexDirection: "column", alignItems: "stretch", gap: 10 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: lgColors.accent }}>
          Runtime cross-check
        </span>
        <span style={lgStatusBadge(!!summary)}>
          {summary ? "Cross-checked" : "Not cross-checked"}
        </span>
        <div style={{ flex: 1 }} />
        <RunActionButton
          label={checking ? "Checking…" : summary ? "Re-check" : "Cross-check"}
          running={checking}
          disabled={disabled}
          iconSize={13}
          style={lgAccentActionButton(color, disabled)}
          onRun={() => startRun.mutate({ scriptKey: "crosscheck" })}
        />
      </div>

      <div style={{ fontSize: 12, color: lgColors.textMuted }}>
        Which declared dependencies actually made it into the built runtime — the SBOM joined
        against the scanned inventory. Per-dependency verdicts appear in the readiness page's
        dependency table.
      </div>

      {!hasReport && sbomReady && (
        <span style={{ fontSize: 11, color: lgColors.textMuted }}>
          Run Evaluate first — the cross-check compares the SBOM against the scanned dependency
          inventory.
        </span>
      )}

      {summary && <CrossCheckResults summary={summary} />}
    </div>
  );
}

/**
 * Aggregates of the cross-check. "Not in runtime" is evidence, not a defect —
 * dev/build-only deps legitimately never reach the runtime — so only the
 * undeclared packages get an itemized list.
 */
function CrossCheckResults({ summary }: { summary: SbomCrossCheckSummary }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <span style={lgStatusBadge(summary.observedMatched === summary.declaredDirectTotal)}>
          {summary.observedMatched}/{summary.declaredDirectTotal} declared deps in runtime
        </span>
        <span style={lgStatusBadge(summary.versionMismatches === 0)}>
          Version mismatches: {summary.versionMismatches}
        </span>
        <span style={lgStatusBadge(summary.undeclaredSameEcosystem === 0)}>
          Undeclared in runtime: {summary.undeclaredSameEcosystem}
        </span>
        <span style={{ fontSize: 11, color: lgColors.textMuted }}>
          {summary.observedTotal} packages observed in total
        </span>
      </div>
      {summary.undeclared.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {summary.undeclared.map((pkg) => (
            <span
              key={`${pkg.ecosystem}:${pkg.name}`}
              style={{
                fontSize: 10,
                fontFamily: F.mono,
                color: "#9333ea",
                background: "#faf5ff",
                border: "1px solid #d8b4fe",
                borderRadius: 99,
                padding: "1px 7px",
                whiteSpace: "nowrap",
              }}
            >
              {pkg.name}
              {pkg.version ? `@${pkg.version}` : ""}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
