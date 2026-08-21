import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
} from "@core/ree-editor/reeEditorViewModel";
import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { CenterSealStrip } from "./CenterSealStrip";
import { SealConfirmCopy } from "./CenterSealStrip/SealConfirmCopy";
import { SealConfirmInclusion } from "./CenterSealStrip/SealConfirmInclusion";
import { SealConfirmWarning } from "./CenterSealStrip/SealConfirmWarning";
import { SealedSealCard } from "./CenterSealStrip/SealedSealCard";
import { SealStatusCard } from "./CenterSealStrip/SealStatusCard";

const cables = [
  { key: "one", label: "One", live: true },
  { key: "two", label: "Two", live: false },
];

describe("seal status surfaces", () => {
  it("toggles available bundle contents and disables unavailable contents", () => {
    const onToggleSource = vi.fn();
    const onToggleRuntime = vi.fn();
    const onToggleResults = vi.fn();
    render(
      <SealConfirmInclusion
        sourceAvailable
        runtimeAvailable
        resultsAvailable={false}
        includeSource
        includeRuntime={false}
        includeResults
        onToggleSource={onToggleSource}
        onToggleRuntime={onToggleRuntime}
        onToggleResults={onToggleResults}
      />,
    );
    expect(screen.getByText("Bundled into the archive")).toBeInTheDocument();
    expect(screen.getByText("Excluded")).toBeInTheDocument();
    expect(screen.getByText("Not in workspace")).toBeInTheDocument();
    const toggles = screen.getAllByRole("button");
    fireEvent.click(toggles[0]);
    fireEvent.click(toggles[1]);
    expect(onToggleSource).toHaveBeenCalledOnce();
    expect(onToggleRuntime).toHaveBeenCalledOnce();
    expect(toggles[2]).toBeDisabled();
    expect(onToggleResults).not.toHaveBeenCalled();
  });

  it.each([
    [true, "All 9 panels are connected"],
    [false, "incomplete data"],
  ])("describes readiness %s", (allLive, text) => {
    const { container } = render(
      <SealConfirmCopy allLive={allLive} totalCables={9} currentLabel="REE evidence" />,
    );
    expect(container).toHaveTextContent(text);
  });

  it("pluralizes missing-panel warnings and omits empty warnings", () => {
    const { rerender } = render(<SealConfirmWarning missing={[{ key: "one", label: "One" }]} />);
    expect(screen.getByText("1 panel not connected")).toBeInTheDocument();
    rerender(
      <SealConfirmWarning
        missing={[
          { key: "one", label: "One" },
          { key: "two", label: "Two" },
        ]}
      />,
    );
    expect(screen.getByText("2 panels not connected")).toBeInTheDocument();
    rerender(<SealConfirmWarning missing={[]} />);
    expect(screen.queryByText(/not connected/)).not.toBeInTheDocument();
  });

  it.each([
    [true, false, "Seal REE"],
    [false, false, "Seal anyway"],
    [false, true, "Sealing…"],
  ] as const)("renders status readiness and running state", (allLive, sealRunning, label) => {
    const onSeal = vi.fn();
    render(
      <SealStatusCard
        sealRef={createRef<HTMLDivElement>()}
        currentLevelMeta={{ color: "blue", label: "REE evidence" }}
        cableItems={cables}
        allLive={allLive}
        totalCables={2}
        missing={allLive ? [] : [{ key: "two", label: "Two" }]}
        sealRunning={sealRunning}
        sourceAvailable
        runtimeAvailable
        resultsAvailable
        includeSource
        includeRuntime
        includeResults
        onToggleSource={vi.fn()}
        onToggleRuntime={vi.fn()}
        onToggleResults={vi.fn()}
        onSeal={onSeal}
      />,
    );
    const button = screen.getByRole("button", { name: new RegExp(label) });
    if (sealRunning) expect(button).toHaveAttribute("aria-busy", "true");
    else expect(button).not.toHaveAttribute("aria-busy");
    fireEvent.click(button);
    expect(onSeal).toHaveBeenCalledTimes(sealRunning ? 0 : 1);
  });

  it("updates inclusion defaults from availability and seals selected content", () => {
    const onSeal = vi.fn();
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
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
    const { rerender } = render(
      <CenterSealStrip
        ree={ree}
        locked={false}
        badges={{}}
        onSeal={onSeal}
        sealRef={createRef<HTMLDivElement>()}
      />,
    );
    const toggles = screen.getAllByRole("button", { pressed: true });
    fireEvent.click(toggles[1]);
    fireEvent.click(screen.getByRole("button", { name: "Seal anyway" }));
    expect(onSeal).toHaveBeenCalledWith({
      includeSource: true,
      includeRuntime: false,
      includeResults: true,
    });

    rerender(
      <CenterSealStrip
        ree={patchReeEditorViewModel(ree, {
          source: { sourceAvailable: false },
          spec: { runtime: "__skipped__", experiments: [] },
        })}
        locked={false}
        badges={{}}
        onSeal={onSeal}
        sealRef={createRef<HTMLDivElement>()}
      />,
    );
    expect(screen.getAllByText("Not in workspace")).toHaveLength(3);
  });

  it("renders sealed metadata with a hash and with fallbacks", () => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      artifact: { sealedAt: "2026-01-01T00:00:00Z", sealHash: "sha256:value" },
    });
    const { rerender } = render(
      <SealedSealCard
        ree={ree}
        sealRef={createRef<HTMLDivElement>()}
        cableItems={cables}
        currentLevelMeta={{ color: "blue", label: "REE evidence" }}
      />,
    );
    expect(screen.getByText("sha256:value")).toBeInTheDocument();
    rerender(
      <SealedSealCard
        ree={createEmptyReeEditorViewModel()}
        sealRef={createRef<HTMLDivElement>()}
        cableItems={cables}
        currentLevelMeta={{ color: "blue", label: "REE evidence" }}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("uses the sealed card through the composed strip", () => {
    render(
      <CenterSealStrip
        ree={patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
          artifact: { sealedAt: "2026-01-01T00:00:00Z", sealHash: "hash" },
        })}
        locked
        badges={{}}
        onSeal={vi.fn()}
        sealRef={createRef<HTMLDivElement>()}
      />,
    );
    expect(screen.getByText("REE SEALED")).toBeInTheDocument();
  });
});
