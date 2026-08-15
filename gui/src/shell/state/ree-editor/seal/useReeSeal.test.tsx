/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { asReeId } from "@core/ree/ReeId";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../../tests/support/renderApp";
import { useReeSeal } from "./useReeSeal";

const sealedDocument = {
  ree_id: "ree-1",
  status: "sealed" as const,
  ree: {
    subject: { definition: { name: "Example REE" } },
    seal: { sealed_at: "2026-01-01T00:00:00Z", ree_digest: "sha256:abc" },
  },
  audit: {
    source: { evidence: "current", payload: "present" },
    runtime: { evidence: "current", payload: "present" },
  },
  workspace_files: [{ path: "README.md", kind: "source", content: "hello", size: 5 }],
  ree_files: [{ path: "artifacts/sbom.json", tag: "Artifact", content: "{}", size: 2 }],
};

describe("useReeSeal", () => {
  it("flushes edits, seals with inclusion options and hydrates the returned workspace", async () => {
    const sealRee = vi.fn().mockResolvedValue(sealedDocument);
    const flushReeIntent = vi.fn().mockResolvedValue(undefined);
    const hydrateWorkspace = vi.fn();
    const showToast = vi.fn();
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { sealRee } }),
    });
    const { result } = renderHook(
      () =>
        useReeSeal({
          reeId: asReeId("ree-1"),
          showToast,
          hydrateWorkspace,
          flushReeIntent,
        }),
      { wrapper: Wrapper },
    );

    await act(() =>
      result.current.handleSealRee({
        includeSource: true,
        includeRuntime: false,
        includeResults: true,
      }),
    );

    expect(flushReeIntent).toHaveBeenCalledBefore(sealRee);
    expect(sealRee).toHaveBeenCalledWith("ree-1", {
      includeSource: true,
      includeRuntime: false,
      includeResults: true,
    });
    expect(hydrateWorkspace).toHaveBeenCalledWith(
      expect.objectContaining({
        workspaceFiles: [expect.objectContaining({ name: "README.md" })],
        reeArtifactFiles: [expect.objectContaining({ name: "artifacts/sbom.json" })],
      }),
    );
    expect(result.current.sealLog?.lines.at(-1)?.type).toBe("ok");
    expect(showToast).toHaveBeenCalledWith("REE sealed — now read-only", "success");
  });

  it("does not call the backend when pending edits cannot be saved", async () => {
    const sealRee = vi.fn();
    const showToast = vi.fn();
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { sealRee } }),
    });
    const { result } = renderHook(
      () =>
        useReeSeal({
          reeId: asReeId("ree-1"),
          showToast,
          hydrateWorkspace: vi.fn(),
          flushReeIntent: vi.fn().mockRejectedValue(new Error("offline")),
        }),
      { wrapper: Wrapper },
    );
    await act(() =>
      result.current.handleSealRee({
        includeSource: false,
        includeRuntime: false,
        includeResults: false,
      }),
    );
    expect(sealRee).not.toHaveBeenCalled();
    expect(result.current.sealLog?.lines.at(-1)?.msg).toBe(
      "Seal failed: could not save pending changes",
    );
    expect(showToast).toHaveBeenCalledWith("Seal failed: could not save pending changes", "error");
  });
});
