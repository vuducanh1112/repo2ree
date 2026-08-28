import { asReeId } from "@core/ree/ReeId";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "./ApiClient";
import { ReeApi } from "./ReeApi";

function harness() {
  const client = {
    request: vi.fn().mockResolvedValue({}),
    requestArrayBuffer: vi.fn().mockResolvedValue(new ArrayBuffer(0)),
    requestArrayBufferWithMeta: vi.fn().mockResolvedValue({
      bytes: new ArrayBuffer(0),
      headers: new Headers(),
    }),
  };
  return { client, api: new ReeApi(client as unknown as ApiClient) };
}

describe("ReeApi", () => {
  it("maps global catalogs and filtered listings", async () => {
    const { api, client } = harness();
    await api.listReeSteps();
    await api.listWorkbenchImages();
    await api.listScriptTemplates();
    await api.listAgents();
    await api.listReeIndex({ cursor: "next page", limit: 20, depositedOnly: true });
    await api.listRees({ cursor: "cursor", limit: 10, status: "sealed" });

    expect(client.request.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/ree-steps",
      "/api/v1/workbench/images",
      "/api/v1/script-templates",
      "/api/v1/agents",
      "/api/v1/ree-index?cursor=next+page&limit=20&deposited_only=true",
      "/api/v1/rees",
    ]);
    expect(client.request.mock.calls[5]?.[2].toString()).toBe(
      "cursor=cursor&limit=10&status=sealed",
    );
  });

  it("maps workspace definitions, source, files, inference and sealing", async () => {
    const { api, client } = harness();
    const reeId = asReeId("ree/1");
    await api.createRee({ name: "REE" });
    await api.getRee(reeId);
    await api.patchReeDefinition(reeId, { definition_patch: { name: "Renamed" } });
    await api.acquireSource(reeId, {
      origin_url: "https://example.test/repo.git",
      source_type: "git",
    });
    await api.removeSource(reeId);
    await api.putFileContent(reeId, { path: "run.sh", content: "echo ok" });
    await api.deleteFileContent(reeId, "dir/a b.txt");
    await api.generateScriptCandidates(reeId, [{ kind: "build" }]);
    await api.lintReeScripts(reeId, [{ kind: "build" }]);
    await api.checkScriptDraft({ kind: "build" }, "set -eu\n", { runtime_path: "runtime.tar" });
    await api.sealRee(reeId, {
      includeSource: true,
      includeRuntime: false,
      includeResults: true,
    });
    await api.deleteRee(reeId);

    expect(client.request.mock.calls.map(([path, init]) => [path, init.method])).toEqual([
      ["/api/v1/rees", "POST"],
      ["/api/v1/rees/ree%2F1", "GET"],
      ["/api/v1/rees/ree%2F1/definition", "PATCH"],
      ["/api/v1/rees/ree%2F1/source:acquire", "POST"],
      ["/api/v1/rees/ree%2F1/source", "DELETE"],
      ["/api/v1/rees/ree%2F1/files/content", "PUT"],
      ["/api/v1/rees/ree%2F1/files/content", "DELETE"],
      ["/api/v1/rees/ree%2F1/script-inferences:generate", "POST"],
      ["/api/v1/rees/ree%2F1/script-lints:run", "POST"],
      ["/api/v1/script-lints:draft", "POST"],
      ["/api/v1/rees/ree%2F1/ree:seal", "POST"],
      ["/api/v1/rees/ree%2F1", "DELETE"],
    ]);
    expect(client.request.mock.calls[6]?.[2].toString()).toBe("path=dir%2Fa+b.txt");
    // The draft carries only the declarations lint reads — no digest, no
    // size: an editor holds neither, and the route no longer asks.
    expect(client.request.mock.calls[9]?.[1].body).toBe(
      '{"target":{"kind":"build"},"source":"set -eu\\n","declarations":{"runtime_path":"runtime.tar"}}',
    );
    expect(client.request.mock.calls[10]?.[1].body).toBe(
      '{"include_source":true,"include_runtime":false,"include_results":true}',
    );
  });

  it("maps upload and bundle lifecycles", async () => {
    const { api, client } = harness();
    const reeId = asReeId("ree-1");
    const payload = { file_name: "source.tgz", size: 3, content_type: "application/gzip" };
    await api.initUpload(reeId, payload);
    await api.completeUpload(reeId, "token", "source.tgz");
    await api.initBundleUpload(reeId, payload);
    await api.loadReeBundle(reeId, "bundle-token", "ree.zip");
    await api.uploadStagedBytes("/api/v1/uploads/token", new Uint8Array([1, 2, 3]).buffer);

    expect(client.request.mock.calls.map(([path, init]) => [path, init.method])).toEqual([
      ["/api/v1/rees/ree-1/source:upload-init", "POST"],
      ["/api/v1/rees/ree-1/source:upload-complete", "POST"],
      ["/api/v1/rees/ree-1/ree:upload-init", "POST"],
      ["/api/v1/rees/ree-1/ree:load", "POST"],
      ["/api/v1/uploads/token", "PUT"],
    ]);
    expect(client.request.mock.calls[4]?.[1].headers).toEqual({
      "Content-Type": "application/octet-stream",
    });
  });

  it("maps reports, reviews and reprovisioning", async () => {
    const { api, client } = harness();
    const reeId = asReeId("ree-1");
    await api.getEvaluateReport(reeId);
    await api.listReviews(reeId);
    await api.startSourceReview(reeId, { basis: "auto" });
    await api.startBuildReview(reeId, "review/1", { basis: "auto", prune_workspace: false });
    await api.startActivationReview(reeId, "review/1");
    await api.startExperimentReview(reeId, "review/1", "hello world");
    await api.reprovisionWorkbench(reeId);

    expect(client.request.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/rees/ree-1/evaluate/report",
      "/api/v1/rees/ree-1/reviews",
      "/api/v1/rees/ree-1/reviews/source:reproduce",
      "/api/v1/rees/ree-1/reviews/review%2F1/build:reproduce",
      "/api/v1/rees/ree-1/reviews/review%2F1/activation:reproduce",
      "/api/v1/rees/ree-1/reviews/review%2F1/experiments/hello%20world:reproduce",
      "/api/v1/rees/ree-1/workbench/reprovision",
    ]);
  });

  it("downloads raw files and extracts archive filenames", async () => {
    const { api, client } = harness();
    const reeId = asReeId("ree-1");
    client.requestArrayBufferWithMeta.mockResolvedValueOnce({
      bytes: new Uint8Array([7]).buffer,
      headers: new Headers({
        "content-disposition": "attachment; filename*=UTF-8''my%20ree.zip",
      }),
    });

    await api.getReeFileBytes(reeId, "results/a.txt");
    const archive = await api.getReeArchive(reeId);

    expect(client.requestArrayBuffer.mock.calls[0]?.[2].toString()).toBe("path=results%2Fa.txt");
    expect(archive.fileName).toBe("my ree.zip");
    expect(Array.from(new Uint8Array(archive.bytes))).toEqual([7]);
  });
});
