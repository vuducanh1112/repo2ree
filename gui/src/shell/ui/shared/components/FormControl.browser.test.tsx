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

    // --field-edge → --palette-edge-steel.
    expect(getComputedStyle(input).borderTopColor).toBe("rgba(95, 142, 190, 0.42)");

    await userEvent.click(input);
    // --field-edge-active → --palette-edge-cyan.
    await expect
      .poll(() => getComputedStyle(input).borderTopColor)
      .toBe("rgba(56, 189, 248, 0.86)");
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
    expect(getComputedStyle(input).backgroundColor).toBe("rgba(241, 245, 249, 0.72)");
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
