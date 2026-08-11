import { describe, expect, it } from "vitest";
import { cssVars, cx } from "./styleVars";

describe("cssVars", () => {
  it("passes calculated custom properties through as style entries", () => {
    expect(cssVars({ "--window-x": "12px", "--window-width": 240 })).toEqual({
      "--window-x": "12px",
      "--window-width": 240,
    });
  });

  it("drops undefined values so a not-yet-measured property falls back to the module", () => {
    expect(cssVars({ "--window-x": "12px", "--window-y": undefined })).toEqual({
      "--window-x": "12px",
    });
  });

  it("returns an empty style object rather than undefined", () => {
    expect(cssVars({})).toEqual({});
  });
});

describe("cx", () => {
  it("joins the class names it is given", () => {
    expect(cx("node", "selected")).toBe("node selected");
  });

  it("drops falsy names, so a conditional class needs no ternary", () => {
    expect(cx("node", false && "busy", null, undefined, "lit")).toBe("node lit");
  });

  it("is empty when nothing applies", () => {
    expect(cx(false, undefined)).toBe("");
  });
});
