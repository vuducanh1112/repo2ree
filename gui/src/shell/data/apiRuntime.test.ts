import { afterEach, describe, expect, it, vi } from "vitest";
import { createApiServices } from "./apiRuntime";

describe("createApiServices", () => {
  afterEach(() => vi.restoreAllMocks());

  it("configures every service with the application API base URL", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ stores: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const services = createApiServices({ baseUrl: "https://api.example.test" });
    await services.reeApi.listStores();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/stores",
      expect.any(Object),
    );
  });
});
