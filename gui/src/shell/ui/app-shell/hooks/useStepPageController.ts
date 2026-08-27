import { authoringStepStatuses } from "@core/app-shell/authoringDag";
import { type AppShellPage, appShellPageForField } from "@core/app-shell/pages";
import { EVIDENCE_STEP_BY_PAGE } from "@core/app-shell/processSteps";
import { auditReceiptRunId, isAuditCurrent } from "@core/ree/StepEvidence";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { defaultParamsForReeStep, REE_STEPS } from "@core/ree-steps/stepCatalog";
import { missingReeStepRequirements } from "@core/ree-steps/stepPolicies";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { ReeStepParamValue } from "@core/ree-steps/stepTypes";
import { activeRunForOperation, latestRunForOperation } from "@core/runs/stepRuns";
import { useReeId } from "@shell/data/apiRuntime";
import { useAuthoringStepsQuery } from "@shell/data/reeSteps/queries";
import { useReeRunsQuery } from "@shell/data/runs/queries";
import type { ReeEditorCommands } from "@shell/state/ree-editor/hooks/createReeEditorCommands";
import { useStepRunLogEntry } from "@shell/state/ree-editor/step-runs/useStepRunLogEntry";
import type { StepRunState } from "@shell/state/ree-editor/store/stepRunState";
import { useCallback, useMemo } from "react";

interface UseStepPageControllerArgs {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  stepRuns: StepRunState;
  commands: Pick<ReeEditorCommands, "setStepParams" | "setPage">;
}

export function useStepPageController({
  page,
  ree,
  stepRuns,
  commands,
}: UseStepPageControllerArgs) {
  const reeId = useReeId();
  const { stepParams } = stepRuns;
  const badges = stepRuns.badges ?? {};
  const timestamps = stepRuns.timestamps ?? {};
  const runs = useReeRunsQuery(reeId).data ?? [];
  const authoringSteps = useAuthoringStepsQuery().data ?? [];
  const step = useMemo(() => REE_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!step) {
      return [];
    }
    const catalogStep = authoringSteps.find((candidate) => candidate.key === step.key);
    if (!catalogStep) {
      return missingReeStepRequirements(step.key, { ...ree.spec, ...ree.source });
    }
    const statuses = authoringStepStatuses(authoringSteps, ree, badges);
    const navigationFieldByStep = {
      source: "sourceAvailable",
      build: "runtime",
      sbom: "sbom",
      evaluate: "sourceAvailable",
    } as const;
    return catalogStep.requires
      .filter((required) => statuses[required] !== "complete")
      .map((required) => ({
        field:
          navigationFieldByStep[required as keyof typeof navigationFieldByStep] ??
          ("name" as const),
        label: authoringSteps.find((candidate) => candidate.key === required)?.label ?? required,
      }));
  }, [step, ree, authoringSteps, badges]);

  const params = useMemo(() => {
    if (!step) {
      return null;
    }
    return (
      (stepParams[step.key] as ReeStepRunParams | undefined) ?? defaultParamsForReeStep(step.key)
    );
  }, [step, stepParams]);

  const setParam = useCallback(
    (paramKey: string, value: ReeStepParamValue) => {
      if (!step) {
        return;
      }

      commands.setStepParams((previous) => ({
        ...previous,
        [step.key]: {
          ...(previous[step.key] ?? defaultParamsForReeStep(step.key)),
          [paramKey]: value,
        },
      }));
    },
    [step, commands],
  );

  const goToRequirements = useCallback(() => {
    const firstMissingField = missing[0]?.field;
    commands.setPage(
      firstMissingField
        ? appShellPageForField(String(firstMissingField))
        : appShellPageForField("name"),
    );
  }, [commands, missing]);

  const activeRun = step ? activeRunForOperation(runs, step.key) : undefined;
  const latestRun = step ? latestRunForOperation(runs, step.key) : undefined;
  const evidenceStep = step ? EVIDENCE_STEP_BY_PAGE[step.key] : undefined;
  const current = evidenceStep ? isAuditCurrent(ree.audit, evidenceStep) : false;
  const receiptRunId = evidenceStep ? auditReceiptRunId(ree.audit, evidenceStep) : undefined;
  const selectedRun = activeRun ?? latestRun;
  const runId = activeRun?.runId ?? (current ? receiptRunId : latestRun?.runId);
  const timestamp =
    selectedRun?.finishedAt ||
    selectedRun?.startedAt ||
    selectedRun?.createdAt ||
    (step ? timestamps[step.key] : undefined);
  const log = useStepRunLogEntry({
    reeId,
    runId,
    fallbackTimestamp: timestamp,
  });

  if (!step || !params) {
    return null;
  }

  const runFailed = latestRun?.status === "failed" || latestRun?.status === "canceled";
  return {
    step,
    log,
    running: !!activeRun,
    runDone: current || !!latestRun,
    runFailed,
    // The catalog badge is an earned marker — a failed run completes the step
    // (Re-run appears) but earns nothing.
    badge: current ? { step: step.key, label: step.outcomeLabel } : null,
    ts: timestamp,
    missing,
    params,
    setParam,
    goToRequirements,
  };
}
