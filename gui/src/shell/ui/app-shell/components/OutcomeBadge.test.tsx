import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutcomeBadge, type StepOutcome } from "./OutcomeBadge";

const outcome: StepOutcome = { step: "activation", label: "Activation passed" };

describe("OutcomeBadge", () => {
  // The component's own doc comment promises this: the outcome is addressable
  // semantically, not by matching styled text. Asserting it by role is what
  // keeps that promise from quietly lapsing.
  it("publishes the outcome as a named status", () => {
    render(<OutcomeBadge outcome={outcome} />);
    expect(screen.getByRole("status", { name: "Activation passed" })).toBeInTheDocument();
  });

  it("shows the label as text as well, for sighted readers", () => {
    render(<OutcomeBadge outcome={outcome} />);
    expect(screen.getByRole("status")).toHaveTextContent("Activation passed");
  });

  // The chip tints from the step it belongs to, so what it must never do is
  // carry a colour of its own — the value it renders is a token reference.
  it("tints from the step rather than from a literal", () => {
    render(<OutcomeBadge outcome={outcome} />);
    expect(screen.getByRole("status")).toHaveStyle({ color: "var(--stage-activation-line)" });
  });
});
