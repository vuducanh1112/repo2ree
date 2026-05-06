import {
  type AssemblyRunCompletionPayload,
  normalizeUiChromePage,
  type SourceOutcomePayload,
} from "../../../application/state/appShellState";
import { createInitialAssemblyRunState } from "../../../application/state/assemblyRunState";
import { createInitialReeDraftState } from "../../../application/state/reeDraft";
import type {
  AppShellAction,
  AppShellContextState,
  SliceName,
  SliceShape,
} from "../../../application/state/types";
import { resolveUpdater } from "../../../application/state/types";
import { createInitialUiChromeState } from "../../../application/state/uiChrome";
import type { ArtifactStatus } from "../../../core/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "../../../core/artifact/sourceOriginRules";
import { createEmptyReeSpec } from "../../../core/ree/ReeSpec";
import type { ReeAssemblyOperationParams } from "../../../core/ree/ReeTypes";
import type { EvaluationState } from "../../../core/review/EvaluationState";
import { computeSourceChangeConsequences } from "../../../core/workspace/sourceChangeConsequences";
import type { WorkspaceSourceState } from "../../../core/workspace/WorkspaceSourceState";

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
    assemblyRun: {
      ...createInitialAssemblyRunState(),
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
  const { reeDraft, assemblyRun } = state;
  return {
    ...state,
    reeDraft: {
      ...reeDraft,
      reeSpec: outcome.reeSpecPatch
        ? { ...reeDraft.reeSpec, ...outcome.reeSpecPatch }
        : reeDraft.reeSpec,
      workspaceSourceState: outcome.workspaceSourceStatePatch
        ? { ...reeDraft.workspaceSourceState, ...outcome.workspaceSourceStatePatch }
        : reeDraft.workspaceSourceState,
      sourceSnapshotArchiveName: outcome.sourceSnapshotArchiveName,
    },
    assemblyRun: {
      ...assemblyRun,
      actionStates: outcome.actionState
        ? { ...assemblyRun.actionStates, source: outcome.actionState }
        : assemblyRun.actionStates,
      badges:
        typeof outcome.badge === "boolean"
          ? { ...assemblyRun.badges, source: outcome.badge }
          : assemblyRun.badges,
      timestamps: outcome.timestamp
        ? { ...assemblyRun.timestamps, source: outcome.timestamp }
        : assemblyRun.timestamps,
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
    assemblyRun: {
      ...state.assemblyRun,
      evaluationState: resolveUpdater(state.assemblyRun.evaluationState, updater),
    },
  };
}

function setAssemblyOperationParams(
  state: AppShellContextState,
  updater: Extract<AppShellAction, { type: "setAssemblyOperationParams" }>["value"],
): AppShellContextState {
  return {
    ...state,
    assemblyRun: {
      ...state.assemblyRun,
      assemblyOperationParams: resolveUpdater(state.assemblyRun.assemblyOperationParams, updater),
    },
  };
}

function setActiveRunId(
  state: AppShellContextState,
  action: Extract<AppShellAction, { type: "setActiveRunId" }>,
): AppShellContextState {
  return {
    ...state,
    assemblyRun: {
      ...state.assemblyRun,
      activeRunIds: {
        ...state.assemblyRun.activeRunIds,
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

function setRepoMode(
  state: AppShellContextState,
  repoMode: "url" | "upload",
): AppShellContextState {
  return {
    ...state,
    reeDraft: {
      ...state.reeDraft,
      repoMode,
    },
  };
}

function setAssemblyRunLoading(state: AppShellContextState, key: string): AppShellContextState {
  return {
    ...state,
    assemblyRun: {
      ...state.assemblyRun,
      actionStates: { ...state.assemblyRun.actionStates, [key]: "loading" },
    },
  };
}

function completeAssemblyRun(
  state: AppShellContextState,
  completion: AssemblyRunCompletionPayload,
): AppShellContextState {
  const { assemblyRun } = state;
  return {
    ...state,
    assemblyRun: {
      ...assemblyRun,
      actionStates: { ...assemblyRun.actionStates, [completion.key]: completion.actionState },
      badges: { ...assemblyRun.badges, [completion.key]: completion.badge },
      timestamps: { ...assemblyRun.timestamps, [completion.key]: completion.timestamp },
    },
  };
}

function resetAssemblyAfterSourceChange(
  state: AppShellContextState,
  assemblyOperationParams: ReeAssemblyOperationParams,
): AppShellContextState {
  const reset = computeSourceChangeConsequences({
    reeSpec: state.reeDraft.reeSpec,
    workspaceSourceState: state.reeDraft.workspaceSourceState,
    artifactStatus: state.reeDraft.artifactStatus,
    evaluationState: state.assemblyRun.evaluationState,
    actionStates: state.assemblyRun.actionStates,
    badges: state.assemblyRun.badges,
    timestamps: state.assemblyRun.timestamps,
    assemblyOperationParams,
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
    assemblyRun: {
      ...state.assemblyRun,
      evaluationState: reset.evaluationState,
      actionStates: reset.actionStates,
      badges: reset.badges,
      timestamps: reset.timestamps,
      assemblyOperationParams: reset.assemblyOperationParams,
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
    case "setAssemblyOperationParams":
      return setAssemblyOperationParams(state, action.value);
    case "setActiveRunId":
      return setActiveRunId(state, action);
    case "setLocked":
      return setLocked(state, action.locked);
    case "setRepoMode":
      return setRepoMode(state, action.repoMode);
    case "setAssemblyRunLoading":
      return setAssemblyRunLoading(state, action.key);
    case "completeAssemblyRun":
      return completeAssemblyRun(state, action.completion);
    case "resetAssemblyAfterSourceChange":
      return resetAssemblyAfterSourceChange(state, action.assemblyOperationParams);
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
