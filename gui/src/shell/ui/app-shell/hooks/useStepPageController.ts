import { type AppShellPage, appShellPageForField, PAGE } from "@core/app-shell/pages";
import { EVIDENCE_STEP_BY_PAGE } from "@core/app-shell/processSteps";
import { auditReceiptRunId, isAuditCurrent } from "@core/ree/StepEvidence";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { defaultParamsForReeStep, REE_STEPS } from "@core/ree-steps/stepCatalog";
import { missingReeStepRequirements } from "@core/ree-steps/stepPolicies";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { ReeStepParamValue } from "@core/ree-steps/stepTypes";
import { activeRunForStep, latestRunForStep } from "@core/runs/stepRuns";
import { useReeId } from "@shell/data/apiRuntime";
import { useRunsAwaitingDocument } from "@shell/data/ree/followRuns";
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
  const timestamps = stepRuns.timestamps ?? {};
  const runs = useReeRunsQuery(reeId).data ?? [];
  const awaitingDocument = useRunsAwaitingDocument(reeId);
  const step = useMemo(() => REE_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!step) {
      return [];
    }
    const authoringSteps = ree.steps.steps;
    const catalogStep = authoringSteps.find((candidate) => candidate.key === step.key);
    if (!catalogStep) {
      return missingReeStepRequirements(step.key, { ...ree.spec, ...ree.source });
    }
    const navigationFieldByStep = {
      [PAGE.ACQUIRE_SOURCE]: "sourceAvailable",
      [PAGE.BUILD_EXPERIMENT_ENVIRONMENT]: "experimentEnvironmentPath",
      [PAGE.GENERATE_SBOM]: "sbom",
      [PAGE.EVALUATE_REPRODUCIBILITY]: "sourceAvailable",
    } as const;
    return catalogStep.requires
      .filter(
        (required) =>
          authoringSteps.find((candidate) => candidate.key === required)?.status !== "complete",
      )
      .map((required) => ({
        field:
          navigationFieldByStep[required as keyof typeof navigationFieldByStep] ??
          ("name" as const),
        label: authoringSteps.find((candidate) => candidate.key === required)?.label ?? required,
      }));
  }, [step, ree]);

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

  const activeRun = step ? activeRunForStep(runs, step.key) : undefined;
  const latestRun = step ? latestRunForStep(runs, step.key) : undefined;
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
  const settling = !!latestRun && awaitingDocument.has(latestRun.runId);
  return {
    step,
    log,
    running: !!activeRun || settling,
    runDone: (current || !!latestRun) && !settling,
    runFailed,
    badge: current ? { step: step.key, label: step.outcomeLabel } : null,
    ts: timestamp,
    missing,
    params,
    setParam,
    goToRequirements,
  };
}
