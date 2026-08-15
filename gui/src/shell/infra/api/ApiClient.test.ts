import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiRequestError } from "./ApiClient";

function json(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", ...init.headers },
    ...init,
  });
}

describe("ApiClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("builds a base URL, query string, merged headers and JSON content type", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ ok: true }));
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      headers: { Authorization: "Bearer token" },
    });

    await expect(
      client.request(
        "items",
        { method: "POST", body: JSON.stringify({ value: 1 }) },
        new URLSearchParams({
          cursor: "a b",
        }),
      ),
    ).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledWith("https://api.example.test/items?cursor=a+b", {
      method: "POST",
      body: '{"value":1}',
      headers: {
        Authorization: "Bearer token",
        "Content-Type": "application/json",
      },
    });
  });

  it("preserves an explicit request content type", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({}));
    const client = new ApiClient();
    await client.request("/upload", {
      method: "PUT",
      body: new Uint8Array([1]).buffer,
      headers: { "Content-Type": "application/octet-stream" },
    });
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toEqual({
      "Content-Type": "application/octet-stream",
    });
  });

  it("returns null for a successful response without JSON", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(new ApiClient().request("/empty")).resolves.toBeNull();
  });

  it("turns a structured error envelope into an actionable error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json(
        {
          error: {
            code: "workbench_busy",
            message: "Workbench is busy",
            retryable: true,
            details: { run_id: "run-1" },
          },
        },
        { status: 409 },
      ),
    );

    const error = await new ApiClient().request("/busy").catch((caught) => caught);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect(error).toMatchObject({
      status: 409,
      code: "workbench_busy",
      message: "Workbench is busy",
      retryable: true,
      details: { run_id: "run-1" },
    });
  });

  it("falls back to HTTP metadata for a non-JSON failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("bad gateway", { status: 502, statusText: "Bad Gateway" }),
    );
    await expect(new ApiClient().request("/down")).rejects.toMatchObject({
      status: 502,
      code: "request_failed",
      message: "Bad Gateway",
      retryable: false,
    });
  });

  it("returns binary bytes and response headers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(new Uint8Array([1, 2, 3]), {
        headers: { "content-disposition": 'attachment; filename="ree.zip"' },
      }),
    );
    const result = await new ApiClient().requestArrayBufferWithMeta("archive");
    expect(Array.from(new Uint8Array(result.bytes))).toEqual([1, 2, 3]);
    expect(result.headers.get("content-disposition")).toContain("ree.zip");
  });

  it("applies structured errors to binary requests too", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json(
        { error: { code: "gone", message: "Archive expired", retryable: false } },
        { status: 410 },
      ),
    );
    await expect(new ApiClient().requestArrayBuffer("archive")).rejects.toMatchObject({
      status: 410,
      code: "gone",
      message: "Archive expired",
    });
  });
});
