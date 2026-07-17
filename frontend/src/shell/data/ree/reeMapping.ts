import type { ReeFile } from "@core/ree/ReeTypes";
import type { ConsistencyReport } from "@core/ree-steps/sealConsistency";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { ReeProject, SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import type {
  ConsistencyReportDto,
  ReeDetailDto,
  SourceRepoMetadataDto,
} from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

// Wire → domain: the API speaks snake_case, the frontend camelCase.
function mapSourceRepo(dto: SourceRepoMetadataDto | undefined): SourceRepoMetadata | undefined {
  if (!dto) {
    return undefined;
  }
  return {
    name: dto.name,
    origin: dto.origin,
    acquiredBy: dto.acquired_by,
    sourceType: dto.source_type,
    swhid: dto.swhid,
    sizeBytes: dto.size_bytes,
    sizeLabel: dto.size_label,
  };
}

function mapConsistency(dto: ConsistencyReportDto | undefined): ConsistencyReport | undefined {
  if (!dto) {
    return undefined;
  }
  return {
    steps: (dto.steps || []).map((step) => ({
      step: step.step,
      status: step.status,
      runId: step.run_id,
      recordedAt: step.recorded_at,
      staleInputs: step.stale_inputs,
      workspaceDrift: step.workspace_drift,
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
  ree: ReeDetailDto,
): ReeProject<FileTreeNode, ReturnType<typeof mapReeDetailToReeSlices>> {
  const files: FileTreeNode[] = [];
  for (const file of ree.files || []) {
    if (!file.path) {
      continue;
    }
    upsertTreeFile(files, file.path, file.content, file.size, file.kind);
  }

  const reeFiles: ReeFile[] = (ree.ree_files || []).map((file, index) => ({
    id: `remote-ree-${index}-${file.path}`,
    name: file.path,
    type: "file",
    tag: file.tag || "REE",
    content: file.content,
    size: file.size,
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
    workbenchImage: ree.workbench_image,
  };
}
