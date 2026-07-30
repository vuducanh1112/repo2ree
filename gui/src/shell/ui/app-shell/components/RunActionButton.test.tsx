import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RunActionButton } from "./RunActionButton";

const base = { label: "Run build", running: false, disabled: false, onRun: () => {} };

describe("RunActionButton", () => {
  // The component's doc comment states this as its reason to exist: the icon is
  // aria-hidden so its <title> ("Play"/"Loading") stays out of the accessible
  // name. Every other test in the suite selects these buttons by label, so the
  // guarantee is load-bearing and worth asserting directly.
  it("is named by its visible label alone, with no icon text leaking in", () => {
    render(<RunActionButton {...base} />);
    expect(screen.getByRole("button", { name: "Run build" })).toBeInTheDocument();
  });

  it("keeps that name while running, when the icon swaps to the spinner", () => {
    render(<RunActionButton {...base} label="Building…" running />);
    expect(screen.getByRole("button", { name: "Building…" })).toBeInTheDocument();
  });

  it("runs on click", async () => {
    const onRun = vi.fn();
    render(<RunActionButton {...base} onRun={onRun} />);

    await userEvent.click(screen.getByRole("button", { name: "Run build" }));

    expect(onRun).toHaveBeenCalledOnce();
  });

  it("does not run while disabled", async () => {
    const onRun = vi.fn();
    render(<RunActionButton {...base} disabled onRun={onRun} />);

    await userEvent.click(screen.getByRole("button", { name: "Run build" }));

    expect(onRun).not.toHaveBeenCalled();
  });

  describe("cancelling", () => {
    it("offers no cancel when the caller cannot handle one", () => {
      render(<RunActionButton {...base} running />);
      expect(screen.getAllByRole("button")).toHaveLength(1);
    });

    it("offers cancel only while the step is actually running", () => {
      const { rerender } = render(<RunActionButton {...base} onCancel={() => {}} />);
      expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();

      rerender(<RunActionButton {...base} running onCancel={() => {}} />);
      expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    });

    it("cancels without also firing the run handler", async () => {
      const onRun = vi.fn();
      const onCancel = vi.fn();
      render(<RunActionButton {...base} running onRun={onRun} onCancel={onCancel} />);

      await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

      expect(onCancel).toHaveBeenCalledOnce();
      expect(onRun).not.toHaveBeenCalled();
    });
  });
});
