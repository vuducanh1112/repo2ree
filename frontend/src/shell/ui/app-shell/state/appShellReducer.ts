import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "@core/artifact/sourceOriginRules";
import { type EvaluationState, emptyEvaluationState } from "@core/evaluate/EvaluationState";
import { createEmptyReeSpec } from "@core/ree/ReeSpec";
import type { ReeStepParams } from "@core/ree/ReeTypes";
import { computeSourceChangeConsequences } from "@core/workspace/sourceChangeConsequences";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import {
  normalizeUiChromePage,
  type SourceOutcomePayload,
  type StepRunCompletionPayload,
} from "./appShellState";
import { createInitialReeIntentState } from "./reeIntent";
import { createInitialReeSessionState } from "./reeSession";
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
  uiChrome: (patch, prev) =>
    patch.page !== undefined
      ? { ...patch, page: normalizeUiChromePage(patch.page, prev.page) }
      : patch,
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
    reeSession: createInitialReeSessionState(normalized),
    stepRuns: {
      ...createInitialStepRunState(),
      evaluationState: normalized.evaluationState,
    },
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
  const { reeIntent, reeSession, stepRuns } = state;
  if (outcome.runId && stepRuns.activeRunIds.source !== outcome.runId) {
    return state;
  }
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
    reeSession: {
      ...reeSession,
      workspaceSourceState: outcome.workspaceSourceStatePatch
        ? { ...reeSession.workspaceSourceState, ...outcome.workspaceSourceStatePatch }
        : reeSession.workspaceSourceState,
    },
    uiChrome: {
      ...state.uiChrome,
      sourceSnapshotArchiveName: outcome.sourceSnapshotArchiveName,
    },
    stepRuns: {
      ...stepRuns,
      actionStates: outcome.actionState
        ? { ...stepRuns.actionStates, source: outcome.actionState }
        : stepRuns.actionStates,
      badges:
        typeof outcome.badge === "boolean"
          ? { ...stepRuns.badges, source: outcome.badge }
          : stepRuns.badges,
      timestamps: outcome.timestamp
        ? { ...stepRuns.timestamps, source: outcome.timestamp }
        : stepRuns.timestamps,
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

function setWorkspaceSourceState(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setWorkspaceSourceState" }>["value"],
): AppShellContextState {
  return {
    ...state,
    reeSession: {
      ...state.reeSession,
      workspaceSourceState: resolveUpdater(state.reeSession.workspaceSourceState, updater),
    },
  };
}

function setArtifactStatus(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setArtifactStatus" }>["value"],
): AppShellContextState {
  return {
    ...state,
    reeSession: {
      ...state.reeSession,
      artifactStatus: resolveUpdater(state.reeSession.artifactStatus, updater),
    },
  };
}

function setEvaluationState(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setEvaluationState" }>["value"],
): AppShellContextState {
  return {
    ...state,
    stepRuns: {
      ...state.stepRuns,
      evaluationState: resolveUpdater(state.stepRuns.evaluationState, updater),
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

function setActiveRunId(
  state: AppShellContextState,
  action: Extract<AppShellAction, { type: "setActiveRunId" }>,
): AppShellContextState {
  return {
    ...state,
    stepRuns: {
      ...state.stepRuns,
      activeRunIds: {
        ...state.stepRuns.activeRunIds,
        [action.key]: action.runId,
      },
    },
  };
}

function cancelStepRun(
  state: AppShellContextState,
  action: Extract<AppShellAction, { type: "cancelStepRun" }>,
): AppShellContextState {
  const activeRunId = state.stepRuns.activeRunIds[action.key];
  if (action.runId && activeRunId && activeRunId !== action.runId) {
    return state;
  }
  const actionStates = { ...state.stepRuns.actionStates };
  const activeRunIds = { ...state.stepRuns.activeRunIds };
  delete actionStates[action.key];
  delete activeRunIds[action.key];
  return {
    ...state,
    stepRuns: {
      ...state.stepRuns,
      actionStates,
      activeRunIds,
    },
  };
}

function setLocked(state: AppShellContextState, locked: boolean): AppShellContextState {
  return {
    ...state,
    uiChrome: { ...state.uiChrome, locked },
  };
}

function setRepoMode(
  state: AppShellContextState,
  repoMode: "url" | "upload",
): AppShellContextState {
  return {
    ...state,
    uiChrome: { ...state.uiChrome, repoMode },
  };
}

function setStepRunLoading(state: AppShellContextState, key: string): AppShellContextState {
  return {
    ...state,
    stepRuns: {
      ...state.stepRuns,
      actionStates: { ...state.stepRuns.actionStates, [key]: "loading" },
    },
  };
}

function completeStepRun(
  state: AppShellContextState,
  completion: StepRunCompletionPayload,
): AppShellContextState {
  const { stepRuns } = state;
  if (completion.runId && stepRuns.activeRunIds[completion.key] !== completion.runId) {
    return state;
  }
  // Keep the active run id after a successful completion: the log panels read
  // it to know which run's logs to render, and clearing it here empties the
  // panel the moment the run finishes. It is cleared on cancel and replaced
  // when the next run starts.
  return {
    ...state,
    stepRuns: {
      ...stepRuns,
      actionStates: { ...stepRuns.actionStates, [completion.key]: completion.actionState },
      badges: { ...stepRuns.badges, [completion.key]: completion.badge },
      timestamps: { ...stepRuns.timestamps, [completion.key]: completion.timestamp },
    },
  };
}

function resetStepsAfterSourceChange(
  state: AppShellContextState,
  stepParams: ReeStepParams,
): AppShellContextState {
  const reset = computeSourceChangeConsequences({
    reeSpec: state.reeIntent.reeSpec,
    workspaceSourceState: state.reeSession.workspaceSourceState,
    artifactStatus: state.reeSession.artifactStatus,
    evaluationState: state.stepRuns.evaluationState,
    actionStates: state.stepRuns.actionStates,
    badges: state.stepRuns.badges,
    timestamps: state.stepRuns.timestamps,
    stepParams,
  });
  return {
    ...state,
    reeIntent: {
      ...state.reeIntent,
      reeSpec: reset.reeSpec,
    },
    reeSession: {
      ...state.reeSession,
      workspaceSourceState: reset.workspaceSourceState,
      artifactStatus: reset.artifactStatus,
    },
    uiChrome: {
      ...state.uiChrome,
      sourceSnapshotArchiveName: reset.sourceSnapshotArchiveName,
    },
    stepRuns: {
      ...state.stepRuns,
      evaluationState: reset.evaluationState,
      actionStates: reset.actionStates,
      badges: reset.badges,
      timestamps: reset.timestamps,
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
    case "setWorkspaceSourceState":
      return setWorkspaceSourceState(state, action.value);
    case "setArtifactStatus":
      return setArtifactStatus(state, action.value);
    case "setEvaluationState":
      return setEvaluationState(state, action.value);
    case "setStepParams":
      return setStepParams(state, action.value);
    case "setActiveRunId":
      return setActiveRunId(state, action);
    case "cancelStepRun":
      return cancelStepRun(state, action);
    case "setLocked":
      return setLocked(state, action.locked);
    case "setRepoMode":
      return setRepoMode(state, action.repoMode);
    case "setStepRunLoading":
      return setStepRunLoading(state, action.key);
    case "completeStepRun":
      return completeStepRun(state, action.completion);
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
