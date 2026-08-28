/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { createEmptyReeExperiment, type ReeExperiment } from "@core/ree/ReeSpec";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExperimentDetail, ExperimentHeaderActions } from "./ExperimentsPageSections";
import type { RunState } from "./useExperimentRun";

vi.mock("@shell/data/scriptTemplates/catalog", () => ({
  useScriptTemplates: () => ({
    data: {
      experiment: {
        run_script_path_pattern: "overlay/experiments/{slug}.sh",
        verify_script_path_pattern: "overlay/experiments/{slug}-verify.sh",
        templates: [],
      },
      verify: [],
    },
  }),
}));
// The analysis panel under each editor has its own tests; this file is about
// what the detail sections render, so its queries are stubbed like the rest.
vi.mock("@shell/data/scriptLint/queries", () => ({
  useScriptDraftLint: () => ({ data: undefined, isFetching: false, error: null }),
  useSavedScriptLint: () => ({ data: undefined, isFetching: false, error: null }),
}));
vi.mock("@shell/data/scriptInference/mutations", () => ({
  useGenerateExperimentScript: () => ({ isPending: false, mutate: vi.fn() }),
}));

function experiment(overrides: Partial<ReeExperiment> = {}): ReeExperiment {
  return {
    ...createEmptyReeExperiment(),
    name: "smoke",
    description: "Smoke test",
    runScript: "overlay/experiments/smoke.sh",
    verifyScript: "overlay/experiments/smoke-verify.sh",
    ...overrides,
  };
}

function runState(overrides: Partial<RunState>): RunState {
  return {
    reeId: "ree-1",
    runId: "run-1",
    status: "succeeded",
    outputs: null,
    failure: null,
    error: null,
    startedAt: "now",
    logLines: [],
    ...overrides,
  };
}

function renderDetail(
  overrides: {
    value?: ReeExperiment;
    otherNames?: string[];
    locked?: boolean;
    state?: RunState | null;
  } = {},
) {
  const onUpdate = vi.fn();
  const onSaveScript = vi.fn();
  const onSaveVerifyScript = vi.fn();
  const onBack = vi.fn();
  render(
    <ExperimentDetail
      experiment={overrides.value ?? experiment()}
      index={1}
      otherNames={overrides.otherNames ?? []}
      locked={overrides.locked ?? false}
      runtimePath={null}
      scriptContent="echo run"
      verifyScriptContent="echo verify"
      onUpdate={onUpdate}
      onSaveScript={onSaveScript}
      onSaveVerifyScript={onSaveVerifyScript}
      onBack={onBack}
      runState={overrides.state ?? null}
    />,
  );
  return { onUpdate, onBack };
}

describe("experiment detail states", () => {
  it("edits every scalar, resource, and output field", () => {
    const { onUpdate, onBack } = renderDetail();
    fireEvent.change(screen.getByPlaceholderText("smoke-test"), { target: { value: "renamed" } });
    fireEvent.change(screen.getByPlaceholderText(/Imports the main package/), {
      target: { value: "description" },
    });
    fireEvent.change(screen.getByPlaceholderText("5-10 min"), { target: { value: "1 min" } });
    fireEvent.change(screen.getByPlaceholderText("4 vCPU sustained"), {
      target: { value: "8 CPU" },
    });
    fireEvent.change(screen.getByLabelText("Output files"), {
      target: { value: " result.txt \n\n report.json " },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save & back/ }));
    expect(onUpdate).toHaveBeenCalledWith({ name: "renamed" });
    expect(onUpdate).toHaveBeenCalledWith({ description: "description" });
    expect(onUpdate).toHaveBeenCalledWith({ runtimeEstimate: "1 min" });
    expect(onUpdate).toHaveBeenCalledWith({
      resourceEstimates: expect.objectContaining({ cpu: "8 CPU" }),
    });
    expect(onUpdate).toHaveBeenCalledWith({ outputPaths: ["result.txt", "report.json"] });
    expect(onBack).toHaveBeenCalledOnce();
  });

  it.each([
    [experiment({ name: "" }), [], "A name is required."],
    [experiment({ name: "same" }), ["same"], "Fix the duplicate name to continue."],
    [experiment({ name: "bad/name" }), [], "Fix the invalid name to continue."],
  ] as const)("explains invalid editable state", (value, otherNames, message) => {
    renderDetail({ value, otherNames: [...otherNames] });
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save & back/ })).toBeDisabled();
  });

  it("renders a locked detail with fallback script paths", () => {
    renderDetail({
      value: experiment({ name: "", runScript: "", verifyScript: "" }),
      locked: true,
    });
    expect(screen.getByText("Edits save automatically.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save & back/ })).toBeEnabled();
  });

  it.each([
    [runState({ status: "running" }), "Running experiment…"],
    [
      runState({
        outputs: { subjectName: "smoke", exitCode: 0, verdict: "pass" },
      }),
      "Command exited 0 — no verify script declared.",
    ],
    [
      runState({
        outputs: { subjectName: "smoke", exitCode: 0, verifyExitCode: 0, verdict: "pass" },
      }),
      "Verify script exited 0 — the declared validation passed.",
    ],
    [
      runState({
        status: "failed",
        outputs: { subjectName: "smoke", exitCode: 0, verifyExitCode: 2, verdict: "fail" },
      }),
      "Verify script failed (exit code 2) — declared validation failed.",
    ],
    [
      runState({
        status: "failed",
        outputs: { subjectName: "smoke", exitCode: null, verdict: "fail" },
      }),
      "Run script failed (exit code ?).",
    ],
    [runState({ status: "canceled" }), "Run canceled — no output data available."],
  ] as const)("renders a run result", (state, message) => {
    renderDetail({ state });
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it("renders typed retryable failures and log output", () => {
    renderDetail({
      state: runState({
        status: "failed",
        failure: {
          category: "unavailable",
          message: "worker offline",
          retryable: true,
          origin: "agent",
        },
        logLines: [{ type: "err", msg: "lost worker" }],
      }),
    });
    expect(screen.getByText("retryable")).toBeInTheDocument();
    expect(screen.getByText("worker offline")).toBeInTheDocument();
  });

  it("wires header run, cancel, and remove actions and hides delete when locked", () => {
    const onRun = vi.fn();
    const onCancel = vi.fn();
    const onRemove = vi.fn();
    const { rerender } = render(
      <ExperimentHeaderActions
        locked={false}
        canRun
        isRunning={false}
        onRun={onRun}
        onCancel={onCancel}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    rerender(
      <ExperimentHeaderActions
        locked
        canRun={false}
        isRunning
        onRun={onRun}
        onCancel={onCancel}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onRun).toHaveBeenCalledOnce();
    expect(onRemove).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
