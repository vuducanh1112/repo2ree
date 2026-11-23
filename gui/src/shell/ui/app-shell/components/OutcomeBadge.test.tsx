import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutcomeBadge, type StepOutcome } from "./OutcomeBadge";

const outcome: StepOutcome = {
  step: "activate_experiment_environment",
  label: "Activation passed",
};

describe("OutcomeBadge", () => {
  it("publishes the outcome as a named status", () => {
    render(<OutcomeBadge outcome={outcome} />);
    expect(screen.getByRole("status", { name: "Activation passed" })).toBeInTheDocument();
  });

  it("shows the label as text as well, for sighted readers", () => {
    render(<OutcomeBadge outcome={outcome} />);
    expect(screen.getByRole("status")).toHaveTextContent("Activation passed");
  });

  it("tints from the step rather than from a literal", () => {
    render(<OutcomeBadge outcome={outcome} />);
    const badge = screen.getByRole("status");
    expect(badge.style.getPropertyValue("--badge-line")).toBe(
      "var(--stage-activate_experiment_environment-line)",
    );
    expect(badge.style.getPropertyValue("--badge-wash")).toBe(
      "var(--stage-activate_experiment_environment-wash)",
    );
  });
});
