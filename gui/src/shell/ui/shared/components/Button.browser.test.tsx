import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cdp, userEvent } from "vitest/browser";
import "../../theme/index.css";
import { Button } from "./Button";

/**
 * The states jsdom cannot answer for. It has no cascade and no layout, so
 * `:hover`, `:focus-visible`, `:active` and `prefers-reduced-motion` all read
 * as "no rule matched" there — a broken stylesheet and a correct one look
 * identical. These run in Chromium and ask for the computed value.
 *
 * That matters most for the claim the primitive is built on: the button owns
 * its interaction states rather than inheriting them from a blanket
 * `button:hover` rule. Only a real engine can tell those two apart.
 */

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
    // matrix(1, 0, 0, 1, 0, -1) — translateY(-1px). Polled because the lift is
    // a transition: read it on the first frame and you get the start value.
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

    // CSS Modules scope keyframe names too, so match the authored stem.
    expect(getComputedStyle(icon).animationName).toContain("button-spin");
    expect(getComputedStyle(icon).animationDuration).toBe("0.9s");

    await emulate("reduce");
    // The policy's 0.01ms, as Chromium serialises it.
    expect(getComputedStyle(icon).animationDuration).toBe("1e-05s");
    expect(getComputedStyle(icon).animationIterationCount).toBe("1");
  });

  it("resolves each variant to a different fill, so the tokens really landed", async () => {
    const { getByRole, rerender } = render(<Button variant="primary">Go</Button>);
    const button = getByRole("button", { name: "Go" });
    // The primary action is the one gradient in the set.
    expect(getComputedStyle(button).backgroundImage).toContain("linear-gradient");

    // Background is transitioned, so each swap is polled rather than sampled.
    rerender(<Button variant="danger">Go</Button>);
    await expect
      .poll(() => getComputedStyle(button).backgroundColor)
      .toBe("rgba(255, 241, 242, 0.82)");

    rerender(
      <Button variant="accent" tint="var(--stage-build-line)">
        Go
      </Button>,
    );
    // --stage-build-line resolves through tones.css to --palette-cyan-600.
    await expect.poll(() => getComputedStyle(button).backgroundColor).toBe("rgb(8, 145, 178)");
  });
});
