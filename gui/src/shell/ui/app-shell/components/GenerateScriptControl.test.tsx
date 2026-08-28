/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import type { ScriptInferenceOutcome } from "@shell/data/scriptInference/mutations";
import type { DecisionTrace } from "@shell/infra/api/apiTypes";
import type { MutationFunctionContext, UseMutationResult } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GenerateScriptControl } from "./GenerateScriptControl";

type GenerateMutation = UseMutationResult<ScriptInferenceOutcome, Error, void>;

function mutation(outcome: ScriptInferenceOutcome | Error, isPending = false): GenerateMutation {
  const mutate: GenerateMutation["mutate"] = (_value, callbacks) => {
    const context = {} as MutationFunctionContext;
    if (outcome instanceof Error) callbacks?.onError?.(outcome, undefined, undefined, context);
    else callbacks?.onSuccess?.(outcome, undefined, undefined, context);
  };
  return {
    isPending,
    mutate,
  } as unknown as GenerateMutation;
}

const trace = {
  dag: "build",
  version: 1,
  steps: [],
  edges: [],
  result_node: "",
} as unknown as DecisionTrace;

describe("GenerateScriptControl", () => {
  it("loads an automatically generated script", () => {
    const onLoad = vi.fn();
    render(
      <GenerateScriptControl
        noun="build script"
        onLoad={onLoad}
        generate={mutation({
          generation: {
            status: "generated",
            script: {
              body: "echo build",
              ruleId: "rule-one",
              application: "automatic_allowed",
              alternativeCount: 1,
              blockingMessages: [],
            },
          },
          trace: null,
          dag: null,
        })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate from repository/ }));
    expect(onLoad).toHaveBeenCalledWith("echo build");
    expect(screen.getByText(/Loaded a generated build script/)).toHaveAttribute("data-tone", "ok");
    expect(screen.queryByText("Decision graph")).not.toBeInTheDocument();
  });

  it.each([
    ["hands over the runtime path a candidate reports", ".repo2ree/artifacts/runtime.tar", 1],
    ["stays silent when the candidate reports none", undefined, 0],
  ] as const)("%s", (_name, runtimePath, calls) => {
    const onRuntimePath = vi.fn();
    render(
      <GenerateScriptControl
        noun="build script"
        onLoad={vi.fn()}
        onRuntimePath={onRuntimePath}
        generate={mutation({
          generation: {
            status: "generated",
            script: {
              body: "echo build",
              ruleId: "rule-one",
              application: "automatic_allowed",
              alternativeCount: 1,
              blockingMessages: [],
              runtimePath,
            },
          },
          trace: null,
          dag: null,
        })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate from repository/ }));
    expect(onRuntimePath).toHaveBeenCalledTimes(calls);
    if (runtimePath) expect(onRuntimePath).toHaveBeenCalledWith(runtimePath);
  });

  it("shows alternatives, warnings, confirmation, and a decision trace", () => {
    render(
      <GenerateScriptControl
        noun="activation script"
        onLoad={vi.fn()}
        generate={mutation({
          generation: {
            status: "generated",
            script: {
              body: "echo activate",
              ruleId: "rule-two",
              application: "confirmation_required",
              alternativeCount: 2,
              blockingMessages: ["Choose an image."],
            },
          },
          trace,
          dag: null,
        })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate from repository/ }));
    expect(screen.getByText(/2 alternatives were available/)).toHaveAttribute("data-tone", "info");
    expect(screen.getByText(/Choose an image/)).toBeInTheDocument();
    expect(screen.getByText("Decision graph")).toBeInTheDocument();
  });

  it.each([
    [undefined, []],
    ["Inspect the source.", ["A manifest is required."]],
  ] as const)("explains a not-inferred result", (notInferredHint, blockingMessages) => {
    render(
      <GenerateScriptControl
        noun="run script"
        notInferredHint={notInferredHint}
        onLoad={vi.fn()}
        generate={mutation({
          generation: { status: "not_inferred", blockingMessages: [...blockingMessages] },
          trace,
          dag: null,
        })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate from repository/ }));
    expect(screen.getByText(/No run script could be inferred/)).toHaveAttribute(
      "data-tone",
      "warn",
    );
  });

  it("reports generation errors and clears an earlier trace", () => {
    const { rerender } = render(
      <GenerateScriptControl
        noun="script"
        onLoad={vi.fn()}
        generate={mutation({
          generation: { status: "not_inferred", blockingMessages: [] },
          trace,
          dag: null,
        })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate from repository/ }));
    expect(screen.getByText("Decision graph")).toBeInTheDocument();
    rerender(
      <GenerateScriptControl
        noun="script"
        onLoad={vi.fn()}
        generate={mutation(new Error("offline"))}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Generate from repository/ }));
    expect(screen.getByText("Generation failed: offline")).toHaveAttribute("data-tone", "error");
    expect(screen.queryByText("Decision graph")).not.toBeInTheDocument();
  });

  it("disables and marks a pending generation", () => {
    render(
      <GenerateScriptControl
        noun="script"
        onLoad={vi.fn()}
        disabled={false}
        generate={mutation(new Error("unused"), true)}
      />,
    );
    expect(screen.getByRole("button", { name: /Generating/ })).toBeDisabled();
  });

  it("honors an explicit disabled state", () => {
    render(
      <GenerateScriptControl
        noun="script"
        onLoad={vi.fn()}
        disabled
        generate={mutation(new Error("unused"))}
      />,
    );
    expect(screen.getByRole("button", { name: /Generate from repository/ })).toBeDisabled();
  });
});
