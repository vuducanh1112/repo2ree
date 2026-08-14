import { asReeId, DEFAULT_REE_ID } from "@core/ree/ReeId";
import { describe, expect, it } from "vitest";
import type { ReeRuntimeValue } from "./apiRuntime";
import { requireReeId, resolveReeId } from "./client";

function runtime(reeId: string): ReeRuntimeValue {
  return {
    reeId: asReeId(reeId),
    reeApi: null as never,
    runsApi: null as never,
  };
}

describe("REE scope resolution", () => {
  it("uses an explicit operation id ahead of the route scope", () => {
    expect(resolveReeId(runtime("ree-from-route"), "ree-explicit")).toBe("ree-explicit");
  });

  it("accepts a provisioned route scope", () => {
    expect(requireReeId(runtime("ree-from-route"))).toBe("ree-from-route");
  });

  it("rejects the unprovisioned sentinel instead of creating a workspace", () => {
    expect(() => requireReeId(runtime(DEFAULT_REE_ID))).toThrow(
      "A provisioned REE is required for this operation",
    );
  });
});
