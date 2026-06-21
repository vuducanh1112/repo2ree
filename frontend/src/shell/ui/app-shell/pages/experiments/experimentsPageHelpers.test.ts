import { describe, expect, it } from "vitest";
import { experimentIndexFromField, expId, isValidExperimentName } from "./experimentsPageHelpers";

describe("experimentIndexFromField", () => {
  it("extracts the index from an experiment field deep-link", () => {
    expect(experimentIndexFromField("experiments[0].name")).toBe(0);
    expect(experimentIndexFromField("experiments[12].command")).toBe(12);
    // The index alone (no trailing field) is enough to target an experiment.
    expect(experimentIndexFromField("experiments[3]")).toBe(3);
  });

  it("returns null for fields that don't target an experiment", () => {
    expect(experimentIndexFromField(null)).toBeNull();
    expect(experimentIndexFromField("")).toBeNull();
    expect(experimentIndexFromField("metadata.name")).toBeNull();
    expect(experimentIndexFromField("experiments")).toBeNull();
    expect(experimentIndexFromField("experiments[].name")).toBeNull();
  });
});

describe("expId", () => {
  it("formats a 1-based, zero-padded id", () => {
    expect(expId(0)).toBe("EXP-001");
    expect(expId(41)).toBe("EXP-042");
  });
});

describe("isValidExperimentName", () => {
  it("accepts empty drafts and plain names, rejects path-unsafe ones", () => {
    expect(isValidExperimentName("")).toBe(true);
    expect(isValidExperimentName("echo-hello")).toBe(true);
    expect(isValidExperimentName("a/b")).toBe(false);
    expect(isValidExperimentName("..")).toBe(false);
  });
});
