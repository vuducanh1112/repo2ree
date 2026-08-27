import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "@core/artifact/sourceOriginRules";
import { type EvaluationState, emptyEvaluationState } from "@core/evaluate/EvaluationState";
import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import type { ReeStepParams } from "@core/ree/ReeTypes";
import { computeSourceChangeConsequences } from "@core/workspace/sourceChangeConsequences";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import { normalizeUiChromePage, type SourceOutcomePayload } from "./appShellState";
import { createInitialReeIntentState } from "./reeIntent";
import { createInitialStepRunState } from "./stepRunState";
import type { AppShellAction, AppShellContextState, SliceName, SliceShape } from "./types";
import { resolveUpdater } from "./types";
import { createInitialUiChromeState } from "./uiChrome";

interface InitialAppShellStateInput {
  reeSpec?: ReturnType<typeof createEmptyReeSpec>;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
}

const sliceNormalizers: {
  [K in SliceName]?: (patch: Partial<SliceShape[K]>, prev: SliceShape[K]) => Partial<SliceShape[K]>;
} = {
  // Keep page navigation normalized at the store boundary so every caller can
  // open the same right-hand workspace drawer with a plain setPage command.
  uiChrome: (patch, prev) => {
    if (patch.page === undefined) return patch;
    const page = normalizeUiChromePage(patch.page, prev.page);
    return { ...patch, page };
  },
};

export function createInitialState(
  initialState: InitialAppShellStateInput = {},
): AppShellContextState {
  const normalized = enforceSourceOriginRules({
    reeSpec: initialState.reeSpec ?? createEmptyReeSpec(),
    workspaceSourceState: initialState.workspaceSourceState ?? { sourceAvailable: false },
    artifactStatus: initialState.artifactStatus ?? { runtimeIncluded: false },
    evaluationState: initialState.evaluationState ?? emptyEvaluationState(),
  });
  return {
    reeIntent: createInitialReeIntentState(normalized),
    stepRuns: createInitialStepRunState(),
    uiChrome: createInitialUiChromeState(),
  };
}

function applyPatch(
  state: AppShellContextState,
  action: Extract<AppShellAction, { type: "patch" }>,
): AppShellContextState {
  const prev = state[action.slice];
  const raw = resolveUpdater(
    prev as Partial<SliceShape[SliceName]>,
    action.updater as (previous: Partial<SliceShape[SliceName]>) => Partial<SliceShape[SliceName]>,
  );
  const normalizer = sliceNormalizers[action.slice] as
    | ((
        patch: Partial<SliceShape[SliceName]>,
        prev: SliceShape[SliceName],
      ) => Partial<SliceShape[SliceName]>)
    | undefined;
  const patch = normalizer ? normalizer(raw, prev as SliceShape[SliceName]) : raw;
  return { ...state, [action.slice]: { ...prev, ...patch } };
}

function applySourceOutcome(
  state: AppShellContextState,
  outcome: SourceOutcomePayload,
): AppShellContextState {
  const { reeIntent } = state;
  // Keep the active run id after a successful source outcome so the source log
  // panel keeps rendering this run's logs; it is cleared on cancel and replaced
  // when the next run starts.
  return {
    ...state,
    reeIntent: {
      ...reeIntent,
      reeSpec: outcome.reeSpecPatch
        ? { ...reeIntent.reeSpec, ...outcome.reeSpecPatch }
        : reeIntent.reeSpec,
    },
  };
}

function updateReeSpec(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "updateReeSpec" }>["value"],
): AppShellContextState {
  return {
    ...state,
    reeIntent: {
      ...state.reeIntent,
      reeSpec: resolveUpdater(state.reeIntent.reeSpec, updater),
    },
  };
}

function setStepParams(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setStepParams" }>["value"],
): AppShellContextState {
  return {
    ...state,
    stepRuns: {
      ...state.stepRuns,
      stepParams: resolveUpdater(state.stepRuns.stepParams, updater),
    },
  };
}

function setRepoMode(
  state: AppShellContextState,
  value: Extract<AppShellAction, { type: "setRepoMode" }>["value"],
): AppShellContextState {
  return {
    ...state,
    uiChrome: { ...state.uiChrome, repoMode: resolveUpdater(state.uiChrome.repoMode, value) },
  };
}

function setFocusedField(
  state: AppShellContextState,
  value: Extract<AppShellAction, { type: "setFocusedField" }>["value"],
): AppShellContextState {
  return {
    ...state,
    uiChrome: {
      ...state.uiChrome,
      focusedField: resolveUpdater(state.uiChrome.focusedField, value),
    },
  };
}

function resetStepsAfterSourceChange(
  state: AppShellContextState,
  stepParams: ReeStepParams,
): AppShellContextState {
  const reset = computeSourceChangeConsequences({
    reeSpec: state.reeIntent.reeSpec,
    workspaceSourceState: { sourceAvailable: false },
    artifactStatus: { runtimeIncluded: false },
    evaluationState: emptyEvaluationState(),
    actionStates: {},
    badges: {},
    timestamps: {},
    stepParams,
  });
  return {
    ...state,
    reeIntent: {
      ...state.reeIntent,
      reeSpec: reset.reeSpec,
    },
    stepRuns: {
      ...state.stepRuns,
      stepParams: reset.stepParams,
    },
  };
}

export function appShellReducer(
  state: AppShellContextState,
  action: AppShellAction,
): AppShellContextState {
  switch (action.type) {
    case "updateReeSpec":
      return updateReeSpec(state, action.value);
    case "setStepParams":
      return setStepParams(state, action.value);
    case "setRepoMode":
      return setRepoMode(state, action.value);
    case "setFocusedField":
      return setFocusedField(state, action.value);
    case "resetStepsAfterSourceChange":
      return resetStepsAfterSourceChange(state, action.stepParams);
    case "showToast":
      return { ...state, uiChrome: { ...state.uiChrome, toast: action.toast } };
    case "clearToast":
      return { ...state, uiChrome: { ...state.uiChrome, toast: null } };
    case "patch":
      return applyPatch(state, action);
    case "applySourceOutcome":
      return applySourceOutcome(state, action.outcome);
    default:
      return state;
  }
}
