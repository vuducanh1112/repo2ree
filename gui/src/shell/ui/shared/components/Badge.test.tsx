import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("is plain text unless a caller asks for a live region", () => {
    const { container } = render(<Badge>3 pinned</Badge>);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(container).toHaveTextContent("3 pinned");
  });

  it("announces an outcome by name when asked, since role=status names from author", () => {
    render(
      <Badge role="status" aria-label="Activation passed">
        Activation passed
      </Badge>,
    );
    expect(screen.getByRole("status", { name: "Activation passed" })).toBeInTheDocument();
  });

  it("publishes a semantic tone as the attribute the module selects on", () => {
    render(<Badge tone="warning">Needs input</Badge>);
    expect(screen.getByText("Needs input")).toHaveAttribute("data-tone", "warning");
  });

  it("takes a domain tone as custom properties and drops the semantic one", () => {
    // A stage-tinted badge has no fixed mood to fall back on: leaving data-tone
    // set would layer the neutral tone under the tint.
    render(
      <Badge
        tint={{
          ink: "var(--stage-build-ink)",
          line: "var(--stage-build-line)",
          wash: "var(--stage-build-wash)",
        }}
      >
        Built
      </Badge>,
    );
    const badge = screen.getByText("Built");
    expect(badge).not.toHaveAttribute("data-tone");
    // Ink and line are published separately: the words take the deep shade, the
    // edge is derived from the mid one.
    expect(badge.style.getPropertyValue("--badge-ink")).toBe("var(--stage-build-ink)");
    expect(badge.style.getPropertyValue("--badge-line")).toBe("var(--stage-build-line)");
    expect(badge.style.getPropertyValue("--badge-wash")).toBe("var(--stage-build-wash)");
  });

  it("keeps its icon out of the accessible name", () => {
    render(
      <Badge role="status" aria-label="Built" icon={<svg role="img" aria-label="Check" />}>
        Built
      </Badge>,
    );
    expect(screen.getByRole("status", { name: "Built" })).toBeInTheDocument();
  });
});
