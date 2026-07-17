import type { ReeFile } from "@core/ree/ReeTypes";
import type { ConsistencyReport } from "@core/ree-steps/sealConsistency";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { ReeProject, SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import type {
  ConsistencyReportWire,
  ReeDocument,
  SourceRepoMetadataWire,
} from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

// Wire → domain: the API speaks snake_case, the frontend camelCase.
function mapSourceRepo(wire: SourceRepoMetadataWire | undefined): SourceRepoMetadata | undefined {
  if (!wire) {
    return undefined;
  }
  return {
    name: wire.name,
    origin: wire.origin,
    acquiredBy: wire.acquired_by,
    sourceType: wire.source_type,
    swhid: wire.swhid,
    sizeBytes: wire.size_bytes,
    sizeLabel: wire.size_label,
  };
}

function mapConsistency(wire: ConsistencyReportWire | undefined): ConsistencyReport | undefined {
  if (!wire) {
    return undefined;
  }
  return {
    steps: (wire.steps || []).map((step) => ({
      step: step.step,
      status: step.status,
      runId: step.run_id ?? undefined,
      recordedAt: step.recorded_at ?? undefined,
      staleInputs: step.stale_inputs,
      workspaceDrift: step.workspace_drift ?? undefined,
    })),
  };
}

function upsertTreeFile(
  roots: FileTreeNode[],
  relativePath: string,
  content: string | undefined,
  size: number | undefined,
  kind: string,
): void {
  const parts = relativePath.split("/").filter(Boolean);
  if (parts.length === 0) {
    return;
  }

  let cursor = roots;
  let prefix = "";
  for (let i = 0; i < parts.length - 1; i += 1) {
    const segment = parts[i];
    prefix = prefix ? `${prefix}/${segment}` : segment;
    let folder = cursor.find((node) => node.type === "folder" && node.name === segment);
    if (!folder) {
      folder = {
        id: `remote-dir-${prefix}`,
        name: segment,
        type: "folder",
        children: [],
      };
      cursor.push(folder);
    }
    if (!folder.children) {
      folder.children = [];
    }
    cursor = folder.children;
  }

  const fileName = parts[parts.length - 1];
  const fileId = `remote-${relativePath}`;
  const fileNode: FileTreeNode = {
    id: fileId,
    name: fileName,
    type: "file",
    content,
    size,
    tag: kind,
  };
  const existingIndex = cursor.findIndex((node) => node.type === "file" && node.name === fileName);
  if (existingIndex >= 0) {
    cursor[existingIndex] = fileNode;
  } else {
    cursor.push(fileNode);
  }
}

export function mapReeDetailToReeProject(
  ree: ReeDocument,
): ReeProject<FileTreeNode, ReturnType<typeof mapReeDetailToReeSlices>> {
  const files: FileTreeNode[] = [];
  for (const file of ree.files || []) {
    if (!file.path) {
      continue;
    }
    upsertTreeFile(files, file.path, file.content ?? undefined, file.size ?? undefined, file.kind);
  }

  const reeFiles: ReeFile[] = (ree.ree_files || []).map((file, index) => ({
    id: `remote-ree-${index}-${file.path}`,
    name: file.path,
    type: "file",
    tag: file.tag || "REE",
    content: file.content ?? undefined,
    size: file.size ?? undefined,
  }));
  const reeState = mapReeDetailToReeSlices(ree);

  return {
    id: ree.ree_id,
    files,
    reeFiles,
    ree: reeState,
    draftManifest: ree.draft_manifest,
    sourceRepo: mapSourceRepo(ree.source_repo),
    consistency: mapConsistency(ree.consistency),
    workbenchImage: ree.workbench_image ?? undefined,
  };
}
