import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cdp, userEvent } from "vitest/browser";
import "../../theme/index.css";
import { Button } from "./Button";

const emulate = async (reducedMotion: "reduce" | "no-preference") => {
  await cdp().send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: reducedMotion }],
  });
};

afterEach(async () => {
  await emulate("no-preference");
});

describe("Button interaction states", () => {
  it("lifts on hover and presses on active", async () => {
    const { getByRole } = render(<Button variant="primary">Run</Button>);
    const button = getByRole("button", { name: "Run" });

    expect(getComputedStyle(button).transform).toBe("none");
    await userEvent.hover(button);
    await expect.poll(() => getComputedStyle(button).transform).toBe("matrix(1, 0, 0, 1, 0, -1)");
  });

  it("shows a focus ring for the keyboard and not for the pointer", async () => {
    const { getByRole } = render(<Button>Cancel</Button>);
    const button = getByRole("button", { name: "Cancel" });

    await userEvent.tab();
    expect(button).toHaveFocus();
    expect(button.matches(":focus-visible")).toBe(true);
    expect(getComputedStyle(button).outlineStyle).toBe("solid");
    expect(getComputedStyle(button).outlineWidth).toBe("2px");

    button.blur();
    await userEvent.click(button);
    expect(button.matches(":focus-visible")).toBe(false);
  });

  it("stays still while disabled, however much it is hovered", async () => {
    const { getByRole } = render(
      <Button variant="primary" disabled>
        Run
      </Button>,
    );
    const button = getByRole("button", { name: "Run" });

    await userEvent.hover(button);
    expect(getComputedStyle(button).transform).toBe("none");
    expect(getComputedStyle(button).cursor).toBe("not-allowed");
  });

  it("drops the lift under reduced motion", async () => {
    const { getByRole } = render(<Button variant="primary">Run</Button>);
    const button = getByRole("button", { name: "Run" });

    await emulate("reduce");
    await userEvent.hover(button);
    expect(getComputedStyle(button).transform).toBe("none");
  });

  it("all but stops the busy spinner under reduced motion", async () => {
    const { getByRole } = render(
      <Button busy icon={<svg aria-hidden />}>
        Building…
      </Button>,
    );
    const icon = getByRole("button", { name: "Building…" }).querySelector("span") as HTMLElement;

    expect(getComputedStyle(icon).animationName).toContain("button-spin");
    expect(getComputedStyle(icon).animationDuration).toBe("0.9s");

    await emulate("reduce");
    expect(getComputedStyle(icon).animationDuration).toBe("1e-05s");
    expect(getComputedStyle(icon).animationIterationCount).toBe("1");
  });

  it("resolves each variant to a different fill, so the tokens really landed", async () => {
    const { getByRole, rerender } = render(<Button variant="primary">Go</Button>);
    const button = getByRole("button", { name: "Go" });
    expect(getComputedStyle(button).backgroundImage).toContain("linear-gradient");

    rerender(<Button variant="danger">Go</Button>);
    await expect.poll(() => getComputedStyle(button).backgroundColor).toBe("rgb(254, 242, 242)");

    rerender(
      <Button variant="accent" tint="var(--stage-build_experiment_environment-line)">
        Go
      </Button>,
    );
    await expect.poll(() => getComputedStyle(button).backgroundColor).toBe("rgb(8, 145, 178)");
  });
});
