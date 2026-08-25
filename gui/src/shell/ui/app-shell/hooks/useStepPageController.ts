import { type AppShellPage, appShellPageForField } from "@core/app-shell/pages";
import { isFailedStepOutcome } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { defaultParamsForReeStep, REE_STEPS } from "@core/ree-steps/stepCatalog";
import { missingReeStepRequirements } from "@core/ree-steps/stepPolicies";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import type { ReeStepParamValue } from "@core/ree-steps/stepTypes";
import { useReeId } from "@shell/data/apiRuntime";
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
  const { badges, stepParams, actionStates, timestamps, activeRunIds } = stepRuns;
  const step = useMemo(() => REE_STEPS.find((step) => step.key === page), [page]);

  const missing = useMemo(() => {
    if (!step) {
      return [];
    }
    return missingReeStepRequirements(step.key, { ...ree.spec, ...ree.source });
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

  const runId = step ? activeRunIds[step.key] : undefined;
  const log = useStepRunLogEntry({
    reeId,
    runId,
    fallbackTimestamp: step ? timestamps[step.key] : undefined,
  });

  if (!step || !params) {
    return null;
  }

  const badgeEntry = badges[step.key];
  const runFailed = isFailedStepOutcome(badgeEntry);
  return {
    step,
    log,
    running: actionStates[step.key] === "loading",
    runDone: !!badgeEntry,
    runFailed,
    // The catalog badge is an earned marker — a failed run completes the step
    // (Re-run appears) but earns nothing.
    badge: badgeEntry && !runFailed ? { step: step.key, label: step.outcomeLabel } : null,
    ts: timestamps[step.key],
    missing,
    params,
    setParam,
    goToRequirements,
  };
}
