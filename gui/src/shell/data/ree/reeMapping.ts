import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { reeFileId, workspaceDirId, workspaceFileId } from "@core/workspace/fileNodeIds";
import type { ReeProject, SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import type { ReeDocument } from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

// Wire → domain: the API speaks snake_case, the GUI camelCase.
function mapSourceRepo(ree: ReeDocument): SourceRepoMetadata | undefined {
  const definition = ree.ree.subject?.definition;
  const source = definition?.source;
  if (!source) {
    return undefined;
  }
  const receipt = ree.ree.subject?.receipts?.source;
  const origin = source.origin_url ?? "";
  return {
    name: definition?.name || origin,
    origin,
    acquiredBy: receipt ? "authoring" : "",
    sourceType: source.source_type,
    swhid: receipt?.observed_swhid ?? "",
    sizeBytes: null,
    sizeLabel: null,
  };
}

// Ids come from `fileNodeIds`, which owns why they are namespaced by inventory
// and derived from the path.
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
        id: workspaceDirId(prefix),
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
  const fileNode: FileTreeNode = {
    id: workspaceFileId(relativePath),
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
  for (const file of ree.workspace_files || []) {
    if (!file.path) {
      continue;
    }
    upsertTreeFile(files, file.path, file.content ?? undefined, file.size ?? undefined, file.kind);
  }

  const reeFiles: ReeFile[] = (ree.ree_files || []).map((file) => ({
    id: reeFileId(file.path),
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
    authorReceipts: parseAuthorReceipts(ree.ree.subject?.receipts),
    sourceRepo: mapSourceRepo(ree),
    workbenchImage: ree.workbench_image ?? undefined,
  };
}
