import { describe, expect, it } from "vitest";
import { DEFAULT_REE_ID } from "../../core/ree/ReeId";
import { createApiRuntime } from "./apiRuntime";

describe("createApiRuntime", () => {
  it("exposes the initial REE id when a default REE id prop is also provided", async () => {
    const runtime = createApiRuntime({
      initialReeId: "ree-from-url",
      reeId: DEFAULT_REE_ID,
    });

    expect(runtime.reeId).toBe("ree-from-url");
    await expect(runtime.ensureReeId(DEFAULT_REE_ID)).resolves.toBe("ree-from-url");
  });

  it("falls back to the default REE id when no initial or explicit id is provided", () => {
    const runtime = createApiRuntime({});

    expect(runtime.reeId).toBe(DEFAULT_REE_ID);
  });
});
