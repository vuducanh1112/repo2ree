import { describe, expect, it } from "vitest";
import { dockerModeCopy, labLoadErrorMessage } from "./labPresentation";

describe("labLoadErrorMessage", () => {
  it("carries the underlying message", () => {
    expect(labLoadErrorMessage(new Error("control plane unavailable"))).toBe(
      "Failed to load labs: control plane unavailable",
    );
  });

  it("falls back for a non-Error rejection", () => {
    expect(labLoadErrorMessage("boom")).toBe("Failed to load labs: unknown error");
  });
});

describe("dockerModeCopy", () => {
  it("describes what per-workbench isolation buys", () => {
    const copy = dockerModeCopy("dind");
    expect(copy.readout).toBe("per-workbench");
    expect(copy.line).toContain("nothing shared");
  });

  it("describes what a shared daemon costs", () => {
    const copy = dockerModeCopy("host");
    expect(copy.readout).toBe("shared daemon");
    expect(copy.line).toContain("alongside other work");
  });

  it("shows an unknown mode verbatim rather than inventing a description", () => {
    const copy = dockerModeCopy("podman");
    expect(copy.readout).toBe("podman");
    expect(copy.line).toBe("Hosts this REE's workbench.");
  });

  it("falls back to a dash when the lab reports no mode", () => {
    expect(dockerModeCopy("").readout).toBe("—");
  });
});
