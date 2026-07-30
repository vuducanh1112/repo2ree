import { describe, expect, it } from "vitest";
import { type ArtifactStatus, isSealed, preserveSeal } from "./ArtifactStatus";

const sealed: ArtifactStatus = {
  runtimeIncluded: true,
  sealedAt: "2026-06-06T00:00:00Z",
  sealHash: "sha256:abc",
};
const unsealed: ArtifactStatus = { runtimeIncluded: false };

describe("isSealed", () => {
  it("requires both a seal time and a seal hash", () => {
    expect(isSealed(sealed)).toBe(true);
    expect(isSealed({ sealedAt: "2026-06-06T00:00:00Z" })).toBe(false);
    expect(isSealed({ sealHash: "sha256:abc" })).toBe(false);
    expect(isSealed(unsealed)).toBe(false);
  });
});

describe("preserveSeal", () => {
  it("keeps the sealed state when an incoming hydration lacks seal stamps", () => {
    // Stale workspace read resolving after the seal must not un-seal the REE.
    expect(preserveSeal(sealed, unsealed)).toBe(sealed);
  });

  it("accepts the incoming state when applying a fresh seal", () => {
    expect(preserveSeal(unsealed, sealed)).toBe(sealed);
  });

  it("accepts the incoming state while still unsealed", () => {
    const next: ArtifactStatus = { runtimeIncluded: true };
    expect(preserveSeal(unsealed, next)).toBe(next);
  });

  it("accepts the incoming state when both are sealed (e.g. re-seal)", () => {
    const reSealed: ArtifactStatus = { ...sealed, sealHash: "sha256:def" };
    expect(preserveSeal(sealed, reSealed)).toBe(reSealed);
  });
});
