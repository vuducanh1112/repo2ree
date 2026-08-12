import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

// jsdom answers what the DOM says, not what the stylesheet computes. So these
// cover semantics and emitted attributes; hover, focus-visible, active and
// reduced motion are in Button.browser.test.tsx, against a real engine.
describe("Button", () => {
  it("defaults to type=button, so one inside a form does not submit it", () => {
    render(<Button>Run</Button>);
    expect(screen.getByRole("button", { name: "Run" })).toHaveAttribute("type", "button");
  });

  it("submits only when a caller asks it to", () => {
    render(<Button type="submit">Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "submit");
  });

  it("keeps the icon out of the accessible name", () => {
    // Every icon here carries a <title> for standalone use. Without aria-hidden
    // that title concatenates into the name and every by-name query breaks.
    render(<Button icon={<svg role="img" aria-label="Play" />}>Run build</Button>);
    expect(screen.getByRole("button", { name: "Run build" })).toBeInTheDocument();
  });

  it("does not fire while disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Run
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("marks a running action busy rather than only spinning its icon", () => {
    render(<Button busy>Building…</Button>);
    expect(screen.getByRole("button", { name: "Building…" })).toHaveAttribute("aria-busy", "true");
  });

  it("is not busy by default, rather than busy=false", () => {
    render(<Button>Run</Button>);
    expect(screen.getByRole("button", { name: "Run" })).not.toHaveAttribute("aria-busy");
  });

  it("publishes its variant and size as the attributes the module selects on", () => {
    render(
      <Button variant="primary" size="small">
        Run
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Run" });
    expect(button).toHaveAttribute("data-variant", "primary");
    expect(button).toHaveAttribute("data-size", "small");
  });

  it("carries a domain tint as a custom property, not as a colour", () => {
    render(
      <Button variant="accent" tint="var(--stage-build-line)">
        Build
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Build" });
    expect(button.style.getPropertyValue("--control-line")).toBe("var(--stage-build-line)");
    expect(button).toHaveAttribute("data-tinted", "true");
  });

  it("is untinted unless asked, so the variant's own colours apply", () => {
    render(<Button variant="secondary">Cancel</Button>);
    expect(screen.getByRole("button", { name: "Cancel" })).not.toHaveAttribute("data-tinted");
  });
});
