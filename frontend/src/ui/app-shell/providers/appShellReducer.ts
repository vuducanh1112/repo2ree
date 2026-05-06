import {
  normalizeUiChromePage,
  type SourceOutcomePayload,
  type WorkflowRunCompletionPayload,
} from "../../../application/state/appShellState";
import { createInitialReeDraftState } from "../../../application/state/reeDraft";
import type {
  AppShellAction,
  AppShellContextState,
  SliceName,
  SliceShape,
} from "../../../application/state/types";
import { resolveUpdater } from "../../../application/state/types";
import { createInitialUiChromeState } from "../../../application/state/uiChrome";
import { createInitialWorkflowRunState } from "../../../application/state/workflowRun";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "../../../domain/artifact/sourceOriginRules";
import { createEmptyReeSpec } from "../../../domain/ree/ReeSpec";
import type { WorkflowParams } from "../../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";

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
    artifactStatus: initialState.artifactStatus ?? {
      runtimeIncluded: false,
      downloadableFiles: [],
    },
    evaluationState: initialState.evaluationState ?? { evalLevel: 0 },
  });
  return {
    reeDraft: {
      ...createInitialReeDraftState(normalized),
      workspaceSourceState: normalized.workspaceSourceState,
      artifactStatus: normalized.artifactStatus,
    },
    workflowRun: {
      ...createInitialWorkflowRunState(),
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
  const { reeDraft, workflowRun } = state;
  return {
    ...state,
    reeDraft: {
      ...reeDraft,
      reeSpec: outcome.reeSpecPatch
        ? { ...reeDraft.reeSpec, ...outcome.reeSpecPatch }
        : reeDraft.reeSpec,
      workspaceSourceState: outcome.workspaceSourceState
        ? { ...reeDraft.workspaceSourceState, ...outcome.workspaceSourceState }
        : reeDraft.workspaceSourceState,
      sourceSnapshotArchiveName: outcome.sourceSnapshotArchiveName,
    },
    workflowRun: {
      ...workflowRun,
      actionStates: outcome.actionState
        ? { ...workflowRun.actionStates, source: outcome.actionState }
        : workflowRun.actionStates,
      badges:
        typeof outcome.badge === "boolean"
          ? { ...workflowRun.badges, source: outcome.badge }
          : workflowRun.badges,
      timestamps: outcome.timestamp
        ? { ...workflowRun.timestamps, source: outcome.timestamp }
        : workflowRun.timestamps,
    },
  };
}

function updateReeSpec(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "updateReeSpec" }>["value"],
): AppShellContextState {
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      reeSpec: resolveUpdater(state.reeDraft.reeSpec, updater),
    },
  };
}

function setWorkspaceSourceState(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setWorkspaceSourceState" }>["value"],
): AppShellContextState {
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      workspaceSourceState: resolveUpdater(state.reeDraft.workspaceSourceState, updater),
    },
  };
}

function setArtifactStatus(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setArtifactStatus" }>["value"],
): AppShellContextState {
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      artifactStatus: resolveUpdater(state.reeDraft.artifactStatus, updater),
    },
  };
}

function setEvaluationState(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setEvaluationState" }>["value"],
): AppShellContextState {
  return {
    ...state,
    workflowRun: {
      ...state.workflowRun,
      evaluationState: resolveUpdater(state.workflowRun.evaluationState, updater),
    },
  };
}

function setWorkflowParams(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setWorkflowParams" }>["value"],
): AppShellContextState {
  return {
    ...state,
    workflowRun: {
      ...state.workflowRun,
      workflowParams: resolveUpdater(state.workflowRun.workflowParams, updater),
    },
  };
}

function setActiveRunId(
  state: AppShellContextState,
  action: Extract<AppShellAction, { type: "setActiveRunId" }>,
): AppShellContextState {
  return {
    ...state,
    workflowRun: {
      ...state.workflowRun,
      activeRunIds: {
        ...state.workflowRun.activeRunIds,
        [action.key]: action.runId,
      },
    },
  };
}

function setLocked(state: AppShellContextState, locked: boolean): AppShellContextState {
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      locked,
    },
  };
}

function setAssemblyRunLoading(state: AppShellContextState, key: string): AppShellContextState {
  return {
    ...state,
    workflowRun: {
      ...state.workflowRun,
      actionStates: { ...state.workflowRun.actionStates, [key]: "loading" },
    },
  };
}

function completeWorkflowRun(
  state: AppShellContextState,
  completion: WorkflowRunCompletionPayload,
): AppShellContextState {
  const { workflowRun } = state;
  return {
    ...state,
    workflowRun: {
      ...workflowRun,
      actionStates: { ...workflowRun.actionStates, [completion.key]: completion.actionState },
      badges: { ...workflowRun.badges, [completion.key]: completion.badge },
      timestamps: { ...workflowRun.timestamps, [completion.key]: completion.timestamp },
    },
  };
}

function resetWorkflowOnSourceChange(
  state: AppShellContextState,
  workflowParams: WorkflowParams,
): AppShellContextState {
  const reset = computeSourceChangeConsequences({
    reeSpec: state.reeDraft.reeSpec,
    workspaceSourceState: state.reeDraft.workspaceSourceState,
    artifactStatus: state.reeDraft.artifactStatus,
    evaluationState: state.workflowRun.evaluationState,
    actionStates: state.workflowRun.actionStates,
    badges: state.workflowRun.badges,
    timestamps: state.workflowRun.timestamps,
    workflowParams,
  });
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      reeSpec: reset.reeSpec,
      workspaceSourceState: reset.workspaceSourceState,
      artifactStatus: reset.artifactStatus,
      sourceSnapshotArchiveName: reset.sourceSnapshotArchiveName,
    },
    workflowRun: {
      ...state.workflowRun,
      evaluationState: reset.evaluationState,
      actionStates: reset.actionStates,
      badges: reset.badges,
      timestamps: reset.timestamps,
      workflowParams: reset.workflowParams,
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
    case "setWorkflowParams":
      return setWorkflowParams(state, action.value);
    case "setActiveRunId":
      return setActiveRunId(state, action);
    case "setLocked":
      return setLocked(state, action.locked);
    case "setAssemblyRunLoading":
      return setAssemblyRunLoading(state, action.key);
    case "completeAssemblyRun":
      return completeWorkflowRun(state, action.completion);
    case "resetAssemblyAfterSourceChange":
      return resetWorkflowOnSourceChange(state, action.workflowParams);
    case "showToast":
      return { ...state, uiChrome: { ...state.uiChrome, toast: action.toast } };
    case "clearToast":
      return { ...state, uiChrome: { ...state.uiChrome, toast: null } };
    case "patch":
      return applyPatch(state, action);
    case "applySourceOutcome":
      return applySourceOutcome(state, action.outcome);
    case "completeWorkflowRun":
      return completeWorkflowRun(state, action.completion);
    case "resetWorkflowOnSourceChange":
      return resetWorkflowOnSourceChange(state, action.workflowParams);
    default:
      return state;
  }
}
