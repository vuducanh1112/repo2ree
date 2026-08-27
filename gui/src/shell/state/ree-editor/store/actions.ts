import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ReeStepParams } from "@core/ree/ReeTypes";
import type { ToastState } from "@core/ree-steps/stepTypes";
import type {
  AppShellAction,
  PatchAction,
  SliceName,
  SliceShape,
  SourceOutcomePayload,
  Updater,
} from "./types";

export const patch = <S extends SliceName>(
  slice: S,
  updater: Updater<Partial<SliceShape[S]>>,
): PatchAction =>
  ({
    type: "patch",
    slice,
    updater,
  }) as PatchAction;

export const applySourceOutcome = (outcome: SourceOutcomePayload): AppShellAction => ({
  type: "applySourceOutcome",
  outcome,
});

export const updateReeSpec = (value: Updater<ReeSpec>): AppShellAction => ({
  type: "updateReeSpec",
  value,
});

export const setStepParams = (value: Updater<ReeStepParams>): AppShellAction => ({
  type: "setStepParams",
  value,
});

export const setRepoMode = (value: Updater<"url" | "upload">): AppShellAction => ({
  type: "setRepoMode",
  value,
});

export const setFocusedField = (value: Updater<string | null>): AppShellAction => ({
  type: "setFocusedField",
  value,
});

export const resetStepsAfterSourceChange = (stepParams: ReeStepParams): AppShellAction => ({
  type: "resetStepsAfterSourceChange",
  stepParams,
});

export const showToast = (toast: ToastState): AppShellAction => ({
  type: "showToast",
  toast,
});

export const clearToast = (): AppShellAction => ({
  type: "clearToast",
});
