import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { userEvent } from "vitest/browser";
import "../../theme/index.css";
import { Field, Input, Textarea } from "./FormControl";

/**
 * Focus is the state a field is judged on, and jsdom cannot evaluate `:focus`
 * against a stylesheet at all. It is also the state a blanket
 * `input:focus { … !important }` used to win — so this is the test that says
 * the primitive really owns its own ring.
 */
describe("FormControl focus states", () => {
  it("takes its focus border from the field, not from a global override", async () => {
    const { getByLabelText } = render(<Input aria-label="Repository" />);
    const input = getByLabelText("Repository");

    // The field consumes the shared neutral border scale.
    expect(getComputedStyle(input).borderTopColor).toBe("rgba(148, 163, 184, 0.35)");

    await userEvent.click(input);
    // Focus promotes that border to the strongest shared accent stop.
    await expect
      .poll(() => getComputedStyle(input).borderTopColor)
      .toBe("rgba(14, 165, 233, 0.58)");
  });

  it("rings for the keyboard", async () => {
    const { getByLabelText } = render(<Input aria-label="Repository" />);
    const input = getByLabelText("Repository");

    await userEvent.tab();
    expect(input).toHaveFocus();
    expect(input.matches(":focus-visible")).toBe(true);
    expect(getComputedStyle(input).outlineWidth).toBe("2px");
  });

  it("greys out and refuses the pointer when disabled", () => {
    const { getByLabelText } = render(<Input aria-label="Repository" disabled />);
    const input = getByLabelText("Repository");
    expect(getComputedStyle(input).cursor).toBe("not-allowed");
    expect(getComputedStyle(input).backgroundColor).toBe("rgba(15, 23, 42, 0.04)");
  });

  it("gives the code flavour a monospace face and the prose one the sans", () => {
    const { getByLabelText } = render(
      <>
        <Textarea aria-label="Script" flavor="code" />
        <Textarea aria-label="Notes" />
      </>,
    );
    expect(getComputedStyle(getByLabelText("Script")).fontFamily).toContain("JetBrains Mono");
    expect(getComputedStyle(getByLabelText("Notes")).fontFamily).toContain("Inter");
  });

  it("puts the label above the control and the hint below it", () => {
    const { getByLabelText, getByText } = render(
      <Field label="Repository" hint="Local path or URL">
        {(bound) => <Input {...bound} />}
      </Field>,
    );
    const label = getByText("Repository").getBoundingClientRect();
    const control = getByLabelText("Repository").getBoundingClientRect();
    const hint = getByText("Local path or URL").getBoundingClientRect();
    expect(label.bottom).toBeLessThanOrEqual(control.top);
    expect(control.bottom).toBeLessThanOrEqual(hint.top);
  });
});
