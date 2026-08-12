import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Surface } from "./Surface";

describe("Surface", () => {
  it("is a separated card by default, which is what every glass page wants", () => {
    const { container } = render(<Surface>panel</Surface>);
    expect(container.firstChild).toHaveAttribute("data-variant", "card");
    expect(container.firstChild).toHaveAttribute("data-spacing", "separated");
  });

  it("names its variants rather than taking a style object", () => {
    const { container } = render(
      <Surface variant="sunken" spacing="flush">
        log
      </Surface>,
    );
    expect(container.firstChild).toHaveAttribute("data-variant", "sunken");
    expect(container.firstChild).toHaveAttribute("data-spacing", "flush");
  });

  it("takes measured geometry as custom properties", () => {
    // The only thing a caller may pass through: a number it computed. Not a
    // colour, not a border — those are the variant's business.
    const { container } = render(<Surface vars={{ "--log-max-height": "240px" }}>log</Surface>);
    const surface = container.firstChild as HTMLElement;
    expect(surface.style.getPropertyValue("--log-max-height")).toBe("240px");
  });
});
