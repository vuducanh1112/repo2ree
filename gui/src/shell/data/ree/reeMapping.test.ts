import { describe, expect, it } from "vitest";
import type { ReeDocument } from "../../infra/api/apiTypes";
import { mapReeDetailToReeProject } from "./reeMapping";

function baseRee(overrides: Partial<ReeDocument> = {}): ReeDocument {
  return {
    ree_id: "ree-1",
    ree: {
      subject: {
        schema_version: 1,
        definition: {
          name: "workspace-demo",
          catalog: {
            description: "",
            version: "",
            website: "",
            keywords: [],
            contributors: [],
          },
          experiments: [],
        },
        receipts: { experiments: {} },
        contents: { entries: [] },
      },
    },
    status: "draft",
    audit: {
      source: { evidence: "missing", payload: "not_applicable", reasons: [] },
      evaluation: { evidence: "missing", payload: "not_applicable", reasons: [] },
      hardware: { evidence: "missing", payload: "not_applicable", reasons: [] },
      runtime: { evidence: "missing", payload: "not_applicable", reasons: [] },
      sbom: { evidence: "missing", payload: "not_applicable", reasons: [] },
      sbom_cross_check: { evidence: "missing", payload: "not_applicable", reasons: [] },
      test_activation: { evidence: "missing", payload: "not_applicable", reasons: [] },
      experiments: [],
    },
    workspace_files: [],
    ree_files: [],
    ...overrides,
  };
}

describe("shell/data/ree/reeMapping", () => {
  it("maps REE files without the removed draft-manifest projection", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        ree_files: [{ path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.reeFiles?.map((file) => file.name)).toEqual(["overlay/build.sh"]);
  });

  it("namespaces node ids per inventory, so one path in both stays two files", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        workspace_files: [{ path: "build.sh", kind: "generated", size: 9 }],
        ree_files: [{ path: "build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.files.map((file) => file.id)).toEqual(["ws:build.sh"]);
    expect(project.reeFiles?.map((file) => file.id)).toEqual(["ree:build.sh"]);
  });

  it("derives ids from the path, so an insertion does not renumber the rest", () => {
    const later = mapReeDetailToReeProject(
      baseRee({
        ree_files: [
          { path: "artifacts/sbom.json", kind: "ree", tag: "Artifact", size: 2 },
          { path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 },
        ],
      }),
    );

    // The console keys its open tabs by node id and prunes any it can no longer
    // find, so an id that moved with its neighbour's arrival would close tabs.
    expect(later.reeFiles?.map((file) => file.id)).toEqual([
      "ree:artifacts/sbom.json",
      "ree:overlay/build.sh",
    ]);
  });

  it("builds nested workspace trees, skips empty paths, and replaces duplicate files", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        workspace_files: [
          { path: "", kind: "source", size: 0 },
          { path: "/src/main.py", kind: "source", size: 1, content: "old" },
          {
            path: "src/helper.py",
            kind: "source",
            size: undefined as unknown as number,
            content: null,
          },
          { path: "src/main.py", kind: "generated", size: 2, content: "new" },
        ],
      }),
    );

    expect(project.files).toEqual([
      {
        id: "ws-dir:src",
        name: "src",
        type: "folder",
        children: [
          {
            id: "ws:src/main.py",
            name: "main.py",
            type: "file",
            content: "new",
            size: 2,
            tag: "generated",
          },
          {
            id: "ws:src/helper.py",
            name: "helper.py",
            type: "file",
            content: undefined,
            size: undefined,
            tag: "source",
          },
        ],
      },
    ]);
  });

  it("maps source metadata with and without a receipt", () => {
    const withReceipt = baseRee();
    const subjectWithReceipt = withReceipt.ree.subject;
    if (!subjectWithReceipt?.definition || !subjectWithReceipt.receipts) {
      throw new Error("incomplete subject fixture");
    }
    subjectWithReceipt.definition.source = {
      origin_url: "https://example.test/repo",
      source_type: "git",
    };
    subjectWithReceipt.receipts.source = {
      schema_version: 1,
      run_id: "run",
      started_at: "start",
      finished_at: "finish",
      duration_ms: 1,
      recorded_at: "recorded",
      operation: "acquire_source",
      origin_url: "https://example.test/repo",
      source_type: "git",
      requested_ref: "main",
      resolved_revision: "abc",
      observed_swhid: "swh:1:dir:value",
      snapshot_digest: "sha256:value",
    };
    const project = mapReeDetailToReeProject({
      ...withReceipt,
      workbench_image: "image:tag",
      ree_files: [
        {
          path: "artifact",
          kind: "ree",
          tag: "",
          size: undefined as unknown as number,
          content: null,
        },
      ],
    });
    expect(project.sourceRepo).toMatchObject({
      name: "workspace-demo",
      acquiredBy: "authoring",
      sourceType: "git",
      swhid: "swh:1:dir:value",
    });
    expect(project.workbenchImage).toBe("image:tag");
    expect(project.reeFiles?.[0]).toMatchObject({
      tag: "REE",
      content: undefined,
      size: undefined,
    });

    const withoutReceipt = baseRee();
    const subjectWithoutReceipt = withoutReceipt.ree.subject;
    if (!subjectWithoutReceipt?.definition) throw new Error("incomplete subject fixture");
    subjectWithoutReceipt.definition.name = "";
    subjectWithoutReceipt.definition.source = {
      origin_url: "https://example.test/fallback",
      source_type: "tarball",
    };
    expect(mapReeDetailToReeProject(withoutReceipt).sourceRepo).toMatchObject({
      name: "https://example.test/fallback",
      acquiredBy: "",
      swhid: "",
    });
  });

  it("defaults absent optional inventories and source metadata", () => {
    const project = mapReeDetailToReeProject(
      baseRee({ workspace_files: undefined, ree_files: undefined, workbench_image: null }),
    );
    expect(project.files).toEqual([]);
    expect(project.reeFiles).toEqual([]);
    expect(project.sourceRepo).toBeUndefined();
    expect(project.workbenchImage).toBeUndefined();
  });
});
