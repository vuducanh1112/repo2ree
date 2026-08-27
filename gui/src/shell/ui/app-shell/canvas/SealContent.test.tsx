import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SealContent } from "./SealContent";

function sealPage(overrides: Partial<Parameters<typeof SealContent>[0]> = {}) {
  return (
    <SealContent
      ree={createEmptyReeEditorViewModel()}
      badges={{}}
      locked={false}
      sealRunning={false}
      sealLog={null}
      onSeal={vi.fn()}
      {...overrides}
    />
  );
}

/** An REE whose source, runtime, and results are all bundleable. */
const bundleableRee = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
  spec: {
    name: "Example",
    runtime: "runtime.tar",
    experiments: [
      {
        name: "experiment",
        description: "",
        runScript: "run.sh",
        verifyScript: "",
        outputPaths: ["result.txt"],
        runtimeEstimate: "",
        resourceEstimates: { cpu: "", memory: "", gpu: "", storage: "", network: "" },
      },
    ],
  },
  source: { sourceAvailable: true },
});

describe("SealContent", () => {
  it("renders as a step page, with the seal offered from the header", () => {
    render(sealPage());

    expect(screen.getByRole("heading", { level: 1, name: "Seal" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Bundle contents" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seal anyway" })).toBeInTheDocument();
  });

  it("counts done steps and names the ones that are not", () => {
    render(sealPage());

    // An empty REE has nothing done, so every step is listed by name rather
    // than as a bare count.
    expect(screen.getByText("0 of 9 steps done")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("9 steps not done");
    expect(screen.getByText("Reproducibility Readiness")).toBeInTheDocument();
    expect(screen.getByText("Experiments")).toBeInTheDocument();
  });

  it("pluralizes a single step that is not done", () => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), { spec: { swhid: "" } });
    render(sealPage({ ree }));

    expect(screen.getByRole("alert")).toHaveTextContent(/steps not done/);
    expect(screen.queryByText(/^1 step not done$/)).not.toBeInTheDocument();
  });

  it("marks the run busy while sealing", () => {
    render(sealPage({ sealRunning: true }));

    const button = screen.getByRole("button", { name: "Sealing…" });
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
  });

  it("toggles bundle contents and seals the selection", () => {
    const onSeal = vi.fn();
    render(sealPage({ ree: bundleableRee, onSeal }));

    const toggles = screen.getAllByRole("button", { pressed: true });
    fireEvent.click(toggles[1]);
    fireEvent.click(screen.getByRole("button", { name: "Seal anyway" }));

    expect(onSeal).toHaveBeenCalledWith({
      includeSource: true,
      includeRuntime: false,
      includeResults: true,
    });
  });

  it("disables contents the workspace does not hold", () => {
    render(
      sealPage({
        ree: patchReeEditorViewModel(bundleableRee, {
          source: { sourceAvailable: false },
          spec: { runtime: "__skipped__", experiments: [] },
        }),
      }),
    );

    expect(screen.getAllByText("Not in workspace")).toHaveLength(3);
  });

  it("shows the sealed record in place of the bundle choices", () => {
    render(
      sealPage({
        locked: true,
        ree: patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
          artifact: { sealedAt: "2026-01-01T00:00:00Z", sealHash: "sha256:value" },
        }),
      }),
    );

    expect(screen.getByRole("status", { name: "REE sealed" })).toHaveTextContent("REE SEALED");
    expect(screen.getByText("sha256:value")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Seal (REE|anyway)$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Bundle contents" })).not.toBeInTheDocument();
  });

  it("falls back when a sealed REE carries no hash", () => {
    render(
      sealPage({
        locked: true,
        ree: patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
          artifact: { sealedAt: "2026-01-01T00:00:00Z" },
        }),
      }),
    );

    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
