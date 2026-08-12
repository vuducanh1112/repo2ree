import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Notice } from "./Notice";

describe("Notice", () => {
  it("announces a danger notice, which appears without the user going looking", () => {
    render(<Notice tone="danger">Required inputs missing</Notice>);
    expect(screen.getByRole("alert")).toHaveTextContent("Required inputs missing");
  });

  it("leaves informational notices silent, so nothing interrupts for a caveat", () => {
    render(<Notice>Runs against the built runtime.</Notice>);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("stacks once it has a heading, so the detail sits under it rather than beside", () => {
    const { container } = render(
      <Notice tone="danger" title="Required inputs missing">
        Name, SBOM
      </Notice>,
    );
    expect(container.firstChild).toHaveAttribute("data-layout", "stacked");
  });

  it("stays a single row without one", () => {
    const { container } = render(<Notice tone="success">All prerequisites met</Notice>);
    expect(container.firstChild).not.toHaveAttribute("data-layout");
    expect(container.firstChild).toHaveAttribute("data-tone", "success");
  });
});
