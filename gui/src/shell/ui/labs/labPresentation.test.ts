import { describe, expect, it } from "vitest";
import {
  allocationStateCopy,
  dockerModeCopy,
  labLoadErrorMessage,
  placementReadout,
} from "./labPresentation";

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
    const copy = dockerModeCopy("docker-nested");
    expect(copy.readout).toBe("per-workbench");
    expect(copy.line).toContain("nothing shared");
  });

  it("describes what a shared daemon costs", () => {
    const copy = dockerModeCopy("docker-host-socket");
    expect(copy.readout).toBe("shared daemon");
    expect(copy.line).toContain("alongside other work");
  });

  it("shows an unknown mode verbatim rather than inventing a description", () => {
    const copy = dockerModeCopy("podman");
    expect(copy.readout).toBe("podman");
    expect(copy.line).toBe("Provides this REE's declared execution capabilities.");
  });

  it("falls back to a dash when the lab reports no mode", () => {
    expect(dockerModeCopy("").readout).toBe("—");
  });
});

describe("placementReadout", () => {
  it("names the profile at its location", () => {
    expect(placementReadout("lab-1", "standard")).toBe("standard @ lab-1");
  });

  it("falls back to whichever half the control plane has reported", () => {
    expect(placementReadout(undefined, "standard")).toBe("standard");
    expect(placementReadout("lab-1", undefined)).toBe("lab-1");
    expect(placementReadout(undefined, undefined)).toBe("Assigned profile");
  });
});

describe("allocationStateCopy", () => {
  it("reads the lifecycle state back as a phrase", () => {
    expect(allocationStateCopy("waiting_for_workbench")).toBe("Waiting for workbench");
    expect(allocationStateCopy("assigned")).toBe("Assigned");
  });

  it("shows a state this build does not know verbatim rather than smoothing it over", () => {
    expect(allocationStateCopy("quarantined")).toBe("quarantined");
  });

  it("says nothing when there is no allocation yet", () => {
    expect(allocationStateCopy(undefined)).toBe("—");
  });
});
