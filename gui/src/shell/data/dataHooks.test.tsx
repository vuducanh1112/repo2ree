/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../tests/support/renderApp";
import { useAgents } from "./agents/agents";
import { useEvaluateReportQuery } from "./evaluate/queries";
import { useAuthorReceiptsQuery } from "./receipts/queries";
import { useUpdateReeIntentMutation } from "./ree/mutations";
import { useReeQuery } from "./ree/queries";
import { useReeIndex } from "./ree-index/reeIndex";
import { useReviewsQuery } from "./reviews/queries";
import { useGenerateBuildScript } from "./scriptInference/mutations";
import { useScriptTemplates } from "./scriptTemplates/catalog";
import { defaultImageRef, useWorkbenchImageCatalog } from "./workbench/images";

describe("shell data hooks", () => {
  it("maps and caches global catalogs", async () => {
    const listAgents = vi.fn().mockResolvedValue({
      agents: [
        {
          agent_id: "b",
          hostname: "z-host",
          version: "1",
          docker_mode: "host",
          connected_at: "2026-01-02T00:00:00Z",
        },
        {
          agent_id: "a",
          hostname: "a-host",
          version: "1",
          docker_mode: "dind",
          connected_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    const listWorkbenchImages = vi.fn().mockResolvedValue({
      images: [{ id: "python", ref: "bench:python", label: "Python", description: "Python tools" }],
      default_id: "python",
    });
    const listScriptTemplates = vi.fn().mockResolvedValue({
      build: { path: "overlay/build.sh", templates: [] },
      activation: {
        run_script_path: "overlay/activate.sh",
        verify_script_path: "overlay/verify.sh",
        templates: [],
      },
      experiment: {
        run_script_pattern: "overlay/{name}.sh",
        verify_script_pattern: "overlay/{name}-verify.sh",
        templates: [],
      },
      verify: [],
    });
    const { Wrapper } = createShellWrapper({
      services: fakeApiServices({ ree: { listAgents, listWorkbenchImages, listScriptTemplates } }),
    });
    const { result } = renderHook(
      () => ({
        agents: useAgents(),
        images: useWorkbenchImageCatalog(),
        templates: useScriptTemplates(),
      }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(result.current.templates.isSuccess).toBe(true));
    expect(result.current.agents.data?.map((agent) => agent.hostname)).toEqual([
      "a-host",
      "z-host",
    ]);
    expect(defaultImageRef(result.current.images.data)).toBe("bench:python");
    expect(defaultImageRef({ images: [], defaultId: "missing" })).toBeUndefined();
    expect(defaultImageRef(undefined)).toBeUndefined();
  });

  it("loads scoped REE resources and transforms index entries", async () => {
    const getRee = vi.fn().mockResolvedValue({
      ree_id: "ree-1",
      ree: { subject: { definition: { name: "Demo" } } },
      status: "draft",
      audit: {
        source: { evidence: "not_applicable", payload: "absent" },
        runtime: { evidence: "not_applicable", payload: "absent" },
      },
      workspace_files: [],
      ree_files: [],
    });
    const getEvaluateReport = vi.fn().mockResolvedValue({ dependencies: [], threats: [] });
    const listAuthorReceipts = vi.fn().mockResolvedValue({ receipts: [] });
    const listReviews = vi.fn().mockResolvedValue({ reviews: [] });
    const listReeIndex = vi.fn().mockResolvedValue({
      items: [
        {
          subject_digest: "sha256:abc",
          name: "Demo",
          sealed_at: "2026-01-01T00:00:00Z",
          catalog_metadata: { description: "Example", keywords: ["demo"] },
          ree_version: "1",
          archive_attestations: [
            {
              archive: "zenodo",
              identifier: "10.1/demo",
              record_url: "https://example.test/demo",
            },
          ],
        },
      ],
      next_cursor: null,
    });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({
        ree: { getRee, getEvaluateReport, listAuthorReceipts, listReviews, listReeIndex },
      }),
    });
    const { result } = renderHook(
      () => ({
        ree: useReeQuery(),
        report: useEvaluateReportQuery({}),
        receipts: useAuthorReceiptsQuery(),
        reviews: useReviewsQuery(),
        index: useReeIndex({ depositedOnly: true }),
      }),
      { wrapper: Wrapper },
    );

    await waitFor(() => {
      expect(result.current.index.isSuccess).toBe(true);
      expect(result.current.ree.isSuccess).toBe(true);
      expect(result.current.report.isSuccess).toBe(true);
      expect(result.current.receipts.isSuccess).toBe(true);
      expect(result.current.reviews.isSuccess).toBe(true);
    });
    expect(result.current.ree.data).toMatchObject({ id: "ree-1" });
    expect(result.current.report.data).toBeNull();
    expect(result.current.receipts.data).toEqual({ receipts: [] });
    expect(result.current.reviews.data).toEqual([]);
    expect(result.current.index.data?.[0]).toMatchObject({
      name: "Demo",
      description: "Example",
      archiveBindings: [{ archive: "zenodo", identifier: "10.1/demo" }],
    });
    expect(listReeIndex).toHaveBeenCalledWith({ depositedOnly: true });
  });

  it("updates intent and runs read-only script inference", async () => {
    const patchReeDefinition = vi.fn().mockResolvedValue({});
    const generateScriptCandidates = vi.fn().mockResolvedValue({
      results: [
        {
          target: { kind: "build" },
          candidates: [
            {
              body: "#!/bin/sh",
              inference_rule: "test-rule",
              application: "automatic_allowed",
            },
          ],
        },
      ],
      dags: [],
    });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { patchReeDefinition, generateScriptCandidates } }),
    });
    const { result } = renderHook(
      () => ({ update: useUpdateReeIntentMutation(), generate: useGenerateBuildScript() }),
      { wrapper: Wrapper },
    );
    await act(() =>
      result.current.update.mutateAsync({
        name: "Demo",
        catalog: {},
        build_runtime: {},
        experiments: [],
        hardware: {},
      }),
    );
    await act(() => result.current.generate.mutateAsync());
    await waitFor(() => expect(result.current.generate.isSuccess).toBe(true));
    expect(patchReeDefinition).toHaveBeenCalledWith("ree-1", {
      definition_patch: expect.objectContaining({ name: "Demo" }),
    });
    expect(generateScriptCandidates).toHaveBeenCalledWith("ree-1", [{ kind: "build" }]);
    expect(result.current.generate.data?.generation).toMatchObject({
      status: "generated",
      script: { body: "#!/bin/sh" },
    });
  });
});
