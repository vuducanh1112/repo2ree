import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusDot } from "./StatusDot";

/** The dot's colours moved into StatusDot.module.css, so what the component
 * still owns — and what the stylesheet now depends on — is the derived state it
 * publishes as `data-state`. */
describe("StatusDot", () => {
  const dotOf = (element: HTMLElement) => element.querySelector("span");

  it("is idle when the step has no result, whatever the staleness says", () => {
    const { container } = render(<StatusDot on={false} stale />);
    expect(dotOf(container)).toHaveAttribute("data-state", "idle");
  });

  it("is ready when the step has a result matching the workspace", () => {
    const { container } = render(<StatusDot on />);
    expect(dotOf(container)).toHaveAttribute("data-state", "ready");
  });

  it("is stale when the result no longer matches the recorded inputs", () => {
    const { container } = render(<StatusDot on stale />);
    expect(dotOf(container)).toHaveAttribute("data-state", "stale");
  });
});
