import { describe, expect, it } from "vitest";
import {
  allocationStateCopy,
  imageReadout,
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

describe("imageReadout", () => {
  it("drops the implicit Docker Hub prefix but keeps the tag", () => {
    expect(imageReadout("docker.io/library/docker:29-dind")).toBe("docker:29-dind");
    expect(imageReadout("docker.io/vuducanh1112/bench:edge")).toBe("vuducanh1112/bench:edge");
  });

  it("leaves a ref from another registry alone", () => {
    expect(imageReadout("ghcr.io/me/bench:v3")).toBe("ghcr.io/me/bench:v3");
  });

  it("truncates a digest rather than hiding that one is pinned", () => {
    expect(imageReadout("docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6")).toBe(
      "docker:29-dind@66d292e5c26b…",
    );
  });

  it("falls back to a dash when nothing has been reported", () => {
    expect(imageReadout("")).toBe("—");
  });
});

describe("placementReadout", () => {
  it("names the image at its location", () => {
    expect(placementReadout("lab-1", "docker.io/library/docker:29-dind")).toBe(
      "docker:29-dind @ lab-1",
    );
  });

  it("falls back to whichever half the control plane has reported", () => {
    expect(placementReadout(undefined, "ghcr.io/me/bench:v3")).toBe("ghcr.io/me/bench:v3");
    expect(placementReadout("lab-1", undefined)).toBe("lab-1");
    expect(placementReadout(undefined, undefined)).toBe("Unassigned bench");
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
