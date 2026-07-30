import type { ReeStepBadge } from "@core/ree-steps/stepTypes";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutcomeBadge } from "./OutcomeBadge";

const badge: ReeStepBadge = { label: "Activation passed", color: "#15803d", bg: "#dcfce7" };

describe("OutcomeBadge", () => {
  // The component's own doc comment promises this: the outcome is addressable
  // semantically, not by matching styled text. Asserting it by role is what
  // keeps that promise from quietly lapsing.
  it("publishes the outcome as a named status", () => {
    render(<OutcomeBadge badge={badge} />);
    expect(screen.getByRole("status", { name: "Activation passed" })).toBeInTheDocument();
  });

  it("shows the label as text as well, for sighted readers", () => {
    render(<OutcomeBadge badge={badge} />);
    expect(screen.getByRole("status")).toHaveTextContent("Activation passed");
  });
});
