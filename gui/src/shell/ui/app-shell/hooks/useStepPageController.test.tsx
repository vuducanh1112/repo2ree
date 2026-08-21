import { PAGE } from "@core/app-shell/pages";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
  type ReeEditorViewModelPatch,
} from "@core/ree-editor/reeEditorViewModel";
import { createInitialStepRunState } from "@shell/state/ree-editor/store/stepRunState";
import { createInitialUiChromeState } from "@shell/state/ree-editor/store/uiChrome";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStepPageController } from "./useStepPageController";

const runQueries = vi.hoisted(() => ({
  run: undefined as
    | {
        runId: string;
        status: "succeeded";
        createdAt: string;
        startedAt?: string;
        finishedAt?: string;
      }
    | undefined,
  lines: undefined as { lines: { type: "info"; msg: string }[]; hasMore: boolean } | undefined,
}));

vi.mock("@shell/data/apiRuntime", () => ({ useReeId: () => "ree-1" }));
vi.mock("@shell/data/runs/queries", () => ({
  useReeRunQuery: () => ({ data: runQueries.run }),
  useReeRunLogsQuery: () => ({ data: runQueries.lines }),
}));

type ControllerArgs = Parameters<typeof useStepPageController>[0];

function controllerArgs(
  overrides: {
    page?: ControllerArgs["uiChrome"]["page"];
    ree?: ReeEditorViewModelPatch;
    stepRuns?: Partial<ControllerArgs["stepRuns"]>;
  } = {},
) {
  const setStepParams = vi.fn();
  const setPage = vi.fn();
  const args = {
    ree: patchReeEditorViewModel(createEmptyReeEditorViewModel(), overrides.ree ?? {}),
    stepRuns: { ...createInitialStepRunState(), ...overrides.stepRuns },
    uiChrome: { ...createInitialUiChromeState(), page: overrides.page ?? PAGE.BUILD },
    commands: { setStepParams, setPage },
  } as unknown as ControllerArgs;
  return { args, setStepParams, setPage };
}

describe("useStepPageController", () => {
  beforeEach(() => {
    runQueries.run = undefined;
    runQueries.lines = undefined;
  });

  it("returns no controller outside a step page", () => {
    const { args } = controllerArgs({ page: PAGE.CANVAS });
    expect(renderHook(() => useStepPageController(args)).result.current).toBeNull();
  });

  it("supplies defaults and directs missing requirements to their editor page", () => {
    const initialStepParams = createInitialStepRunState().stepParams;
    const { args, setPage, setStepParams } = controllerArgs({
      page: PAGE.EVALUATE,
      ree: { source: { sourceAvailable: false } },
      stepRuns: { stepParams: initialStepParams },
    });
    const { result } = renderHook(() => useStepPageController(args));

    expect(result.current?.params).toEqual({ strict: false });
    expect(result.current?.missing).toEqual([
      { field: "sourceAvailable", label: "Source loaded in workspace" },
    ]);

    act(() => result.current?.setParam("strict", true));
    const update = setStepParams.mock.calls[0][0];
    expect(update(initialStepParams).evaluate).toEqual({ strict: true });

    act(() => result.current?.goToRequirements());
    expect(setPage).toHaveBeenCalledWith(PAGE.SOURCE);
  });

  it("preserves existing parameters and falls back to metadata when nothing is missing", () => {
    const stepParams = {
      ...createInitialStepRunState().stepParams,
      evaluate: { strict: true },
    };
    const { args, setPage, setStepParams } = controllerArgs({
      page: PAGE.EVALUATE,
      ree: { source: { sourceAvailable: true } },
      stepRuns: { stepParams },
    });
    const { result } = renderHook(() => useStepPageController(args));

    expect(result.current?.params).toEqual({ strict: true });
    act(() => result.current?.setParam("strict", false));
    const update = setStepParams.mock.calls[0][0];
    expect(update(stepParams).evaluate).toEqual({ strict: false });
    act(() => result.current?.goToRequirements());
    expect(setPage).toHaveBeenCalledWith(PAGE.METADATA);
  });

  it.each([
    ["succeeded", false, true],
    ["failed", true, false],
    ["canceled", true, false],
  ] as const)("maps a %s outcome to failure and badge state", (outcome, failed, earned) => {
    const { args } = controllerArgs({
      stepRuns: {
        badges: { build: outcome },
        actionStates: { build: "loading" },
        timestamps: { build: "fallback" },
      },
    });
    const { result } = renderHook(() => useStepPageController(args));

    expect(result.current).toMatchObject({
      running: true,
      runDone: true,
      runFailed: failed,
      ts: "fallback",
    });
    expect(!!result.current?.badge).toBe(earned);
  });

  it.each([
    [{ finishedAt: "finished", startedAt: "started", createdAt: "created" }, "finished"],
    [{ startedAt: "started", createdAt: "created" }, "started"],
    [{ createdAt: "created" }, "created"],
    [{ createdAt: "" }, "fallback"],
  ])("uses the run timestamp fallback chain", (timestamps, expected) => {
    runQueries.run = { runId: "run-1", status: "succeeded", ...timestamps };
    runQueries.lines = {
      lines: [{ type: "info", msg: "building" }],
      hasMore: false,
    };
    const { args } = controllerArgs({
      stepRuns: {
        activeRunIds: { build: "run-1" },
        timestamps: { build: "fallback" },
      },
    });

    expect(renderHook(() => useStepPageController(args)).result.current?.log).toEqual({
      lines: [{ type: "info", msg: "building" }],
      ts: expected,
    });
  });

  it("returns an empty log and generated timestamp when the run has no data", () => {
    const { args } = controllerArgs({
      stepRuns: { activeRunIds: { build: "run-1" } },
    });
    const before = Date.now();
    const log = renderHook(() => useStepPageController(args)).result.current?.log;
    expect(log?.lines).toEqual([]);
    expect(Date.parse(log?.ts ?? "")).toBeGreaterThanOrEqual(before);
  });
});
