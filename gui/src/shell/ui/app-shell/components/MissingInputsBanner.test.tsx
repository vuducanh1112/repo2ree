import type { ReeStepRequirement } from "@core/ree-steps/stepTypes";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MissingInputsBanner } from "./MissingInputsBanner";

// `field` is keyed to the spec/source state, so these are the real requirements
// stepPolicies declares for the build and SBOM steps, not invented names.
const missing: ReeStepRequirement[] = [
  { field: "sourceAvailable", label: "Source available" },
  { field: "runtime", label: "Runtime" },
];

describe("MissingInputsBanner", () => {
  it("renders nothing when nothing is missing", () => {
    const { container } = render(<MissingInputsBanner missing={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names every missing input", () => {
    render(<MissingInputsBanner missing={missing} />);
    expect(screen.getByText("Source available")).toBeInTheDocument();
    expect(screen.getByText("Runtime")).toBeInTheDocument();
  });

  it("offers no jump-back button when the caller cannot handle one", () => {
    render(<MissingInputsBanner missing={missing} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("jumps back to the fields on request", async () => {
    const onGoFields = vi.fn();
    render(<MissingInputsBanner missing={missing} onGoFields={onGoFields} />);

    await userEvent.click(screen.getByRole("button", { name: "Jump to required field" }));

    expect(onGoFields).toHaveBeenCalledOnce();
  });

  it("takes a caller-supplied label for that button", () => {
    render(
      <MissingInputsBanner missing={missing} onGoFields={() => {}} goLabel="Back to metadata" />,
    );
    expect(screen.getByRole("button", { name: "Back to metadata" })).toBeInTheDocument();
  });
});
