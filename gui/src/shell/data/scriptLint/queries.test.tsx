/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */

import type { LintReport, ScriptTargetSelector } from "@shell/infra/api/apiTypes";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../tests/support/renderApp";
import { selectReport, useSavedScriptLint, useScriptDraftLint } from "./queries";

function report(
  kind: ScriptTargetSelector["kind"] = "build",
  experimentName: string | null = null,
): LintReport {
  return {
    schema_version: 1,
    engine_version: "1",
    target: { kind, experiment_name: experimentName, path: `ree-scripts/${kind}.sh` },
    findings: [],
    tiers: [{ tier: "contract", status: "ran" }],
  } as LintReport;
}

describe("selectReport", () => {
  it("finds the report for the requested target", () => {
    const response = { reports: [report("build"), report("activation_run")], missing_scripts: [] };
    expect(selectReport(response, { kind: "activation_run" })?.target.kind).toBe("activation_run");
  });

  it("matches an experiment by name, not by kind alone", () => {
    const response = {
      reports: [report("experiment_run", "a"), report("experiment_run", "b")],
      missing_scripts: [],
    };
    const found = selectReport(response, { kind: "experiment_run", experimentName: "b" });
    expect(found?.target.experiment_name).toBe("b");
  });

  it("returns nothing for a script that is not written yet", () => {
    const response = { reports: [], missing_scripts: ["ree-scripts/build_script.sh"] };
    expect(selectReport(response, { kind: "build" })).toBeUndefined();
  });

  it("returns nothing when the call itself produced nothing", () => {
    expect(selectReport(undefined, { kind: "build" })).toBeUndefined();
  });
});

describe("useScriptDraftLint", () => {
  it("checks the draft against the declarations it is given", async () => {
    const checkScriptDraft = vi.fn().mockResolvedValue(report());
    const { Wrapper } = createShellWrapper({
      services: fakeApiServices({ ree: { checkScriptDraft } }),
    });

    const { result } = renderHook(
      () =>
        useScriptDraftLint({ kind: "build" }, "docker build .\n", "runtime.tar", { enabled: true }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(checkScriptDraft).toHaveBeenCalledWith({ kind: "build" }, "docker build .\n", {
      runtime_path: "runtime.tar",
    });
  });

  it("asks nothing of an empty editor", async () => {
    const checkScriptDraft = vi.fn().mockResolvedValue(report());
    const { Wrapper } = createShellWrapper({
      services: fakeApiServices({ ree: { checkScriptDraft } }),
    });

    renderHook(() => useScriptDraftLint({ kind: "build" }, "   \n", null, { enabled: true }), {
      wrapper: Wrapper,
    });

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(checkScriptDraft).not.toHaveBeenCalled();
  });

  it("asks nothing while checks are disabled", async () => {
    const checkScriptDraft = vi.fn().mockResolvedValue(report());
    const { Wrapper } = createShellWrapper({
      services: fakeApiServices({ ree: { checkScriptDraft } }),
    });

    renderHook(() => useScriptDraftLint({ kind: "build" }, "set -eu\n", null, { enabled: false }), {
      wrapper: Wrapper,
    });

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(checkScriptDraft).not.toHaveBeenCalled();
  });
});

describe("useSavedScriptLint", () => {
  it("reduces the workbench response to this target's report", async () => {
    const lintReeScripts = vi
      .fn()
      .mockResolvedValue({ reports: [report("build")], missing_scripts: [] });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { lintReeScripts } }),
    });

    const { result } = renderHook(
      () => useSavedScriptLint({ kind: "build" }, "docker build .\n", { enabled: true }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.target.kind).toBe("build");
  });

  it("asks nothing while the editor is dirty", async () => {
    const lintReeScripts = vi.fn().mockResolvedValue({ reports: [], missing_scripts: [] });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { lintReeScripts } }),
    });

    renderHook(() => useSavedScriptLint({ kind: "build" }, "x\n", { enabled: false }), {
      wrapper: Wrapper,
    });

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(lintReeScripts).not.toHaveBeenCalled();
  });
});
