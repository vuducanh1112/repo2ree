import type { ReviewAttempt, ReviewExperimentComparison } from "@core/reviews/Review";
import type { ReviewStepKey, ReviewStepStatus } from "@core/reviews/reviewDag";
import { experimentReviewStatus, reproducedExperimentCount } from "@core/reviews/reviewStatuses";
import { Ic } from "../../../shared/components/Icon";
import { C, F } from "../../../theme/theme";

const VERDICT_META: Partial<Record<ReviewStepStatus, { label: string; color: string }>> = {
  ready: { label: "Ready", color: C.textMuted },
  queued: { label: "Queued", color: "#d97706" },
  running: { label: "Running", color: C.accent },
  identical: { label: "Identical", color: C.done },
  reproduced: { label: "Reproduced", color: C.done },
  different: { label: "Different", color: "#d97706" },
  inconclusive: { label: "Inconclusive", color: C.textMuted },
  unavailable: { label: "Locked", color: C.textMuted },
};

/**
 * Per-experiment reproduction, plus a sweep over all of them.
 *
 * A list rather than one button because an REE's experiments are independent
 * claims: a reviewer reproducing a paper's headline result should not have to
 * sit through five others, and a verdict that differs belongs to *one*
 * experiment rather than to the step. "Run all" is a convenience over the same
 * per-experiment path — it dispatches them one at a time, because they share a
 * workspace and concurrent runs would interleave their output files.
 */
export function ExperimentReviewPanel({
  attempt,
  experimentNames,
  statuses,
  sweeping,
  canRun,
  onRun,
  onRunAll,
}: {
  attempt: ReviewAttempt | undefined;
  experimentNames: readonly string[];
  statuses: Readonly<Record<ReviewStepKey, ReviewStepStatus>>;
  sweeping: boolean;
  canRun: boolean;
  onRun: (experimentName: string) => void;
  onRunAll: () => void;
}) {
  if (experimentNames.length === 0) return null;
  // What reproduced, not what ran: an experiment that came back `different` has
  // a verdict but is not a success, and this counter carries the word
  // "reproduced" next to it.
  const reproduced = reproducedExperimentCount(attempt);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            flex: 1,
            color: C.textMuted,
            fontFamily: F.mono,
            fontSize: 9,
            fontWeight: 800,
            letterSpacing: 0.4,
          }}
        >
          RESULTS · {reproduced}/{experimentNames.length} REPRODUCED
        </span>
        <button
          type="button"
          onClick={onRunAll}
          disabled={!canRun || sweeping}
          aria-label="Reproduce all experiments"
          style={{
            minHeight: 26,
            padding: "0 10px",
            display: "flex",
            alignItems: "center",
            gap: 6,
            border: `1px solid ${!canRun || sweeping ? C.border : C.accent}`,
            borderRadius: 7,
            background: C.surfaceAlt,
            color: !canRun || sweeping ? C.textMuted : C.text,
            cursor: !canRun || sweeping ? "not-allowed" : "pointer",
            fontFamily: F.mono,
            fontSize: 9.5,
            fontWeight: 750,
          }}
        >
          {sweeping ? Ic.loader(12) : Ic.play(12)}
          <span>{sweeping ? "Running all" : "Run all"}</span>
        </button>
      </div>

      {experimentNames.map((name) => (
        <ExperimentRow
          key={name}
          name={name}
          status={experimentReviewStatus(attempt, name, statuses)}
          comparison={attempt?.experimentComparisons.find((entry) => entry.experimentName === name)}
          canRun={canRun && !sweeping}
          onRun={onRun}
        />
      ))}
    </div>
  );
}

function ExperimentRow({
  name,
  status,
  comparison,
  canRun,
  onRun,
}: {
  name: string;
  status: ReviewStepStatus;
  comparison: ReviewExperimentComparison | undefined;
  canRun: boolean;
  onRun: (experimentName: string) => void;
}) {
  const meta = VERDICT_META[status] ?? { label: status, color: C.textMuted };
  const disabled = !canRun || status === "unavailable" || status === "running";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "5px 8px",
        border: `1px solid ${C.border}`,
        borderRadius: 7,
        background: C.surfaceAlt,
      }}
    >
      <span
        style={{
          flex: 1,
          minWidth: 0,
          color: C.text,
          fontSize: 10.5,
          fontWeight: 650,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={name}
      >
        {name}
      </span>
      {comparison ? <CriterionNote comparison={comparison} /> : null}
      <span
        style={{
          color: meta.color,
          fontFamily: F.mono,
          fontSize: 8.5,
          fontWeight: 800,
          whiteSpace: "nowrap",
        }}
      >
        {meta.label.toUpperCase()}
      </span>
      <button
        type="button"
        onClick={() => onRun(name)}
        disabled={disabled}
        aria-label={`Reproduce experiment ${name}`}
        style={{
          minHeight: 22,
          padding: "0 8px",
          border: `1px solid ${C.border}`,
          borderRadius: 6,
          background: C.surface,
          color: disabled ? C.textMuted : C.text,
          cursor: disabled ? "not-allowed" : "pointer",
          fontFamily: F.mono,
          fontSize: 9,
          fontWeight: 750,
        }}
      >
        {comparison ? "Re-run" : "Run"}
      </button>
    </div>
  );
}

/**
 * What the verdict rests on, in the one line there is room for.
 *
 * A `reproduced` verdict is worth exactly as much as the verify script that
 * granted it, so the script is named rather than hidden — and an experiment
 * that declares none says so, since that is why its verdict is inconclusive
 * rather than a pass.
 */
function CriterionNote({ comparison }: { comparison: ReviewExperimentComparison }) {
  const criterion = comparison.verifyScriptPath.trim();
  const note = !criterion
    ? "no verify script"
    : comparison.expectedVerifyExitCode == null
      ? "no author baseline"
      : comparison.expectedVerifyScriptDigest == null
        ? "author criterion unbound"
        : comparison.verifyScriptDigest !== comparison.expectedVerifyScriptDigest
          ? "criterion changed"
          : criterion;

  return (
    <span
      style={{
        color: C.textMuted,
        fontFamily: F.mono,
        fontSize: 8.5,
        maxWidth: 190,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
      title={
        criterion
          ? `criterion: ${criterion}${
              comparison.verifyScriptDigest ? ` (${comparison.verifyScriptDigest})` : ""
            }`
          : "this experiment declares no verify script, so nothing states what a correct result is"
      }
    >
      {note}
    </span>
  );
}
