import type { ReeFile } from "../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import type { ReeProject } from "../../../core/workspace/WorkspaceTypes";
import type { ReeDetailDto } from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

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

  const reeFiles: ReeFile[] = (ree.reeFiles || []).map((file, index) => ({
    id: `remote-ree-${index}-${file.path}`,
    name: file.path,
    type: "file",
    tag: file.tag || "REE",
    content: file.content,
    size: file.size,
  }));
  const reeState = mapReeDetailToReeSlices(ree);

  return {
    id: ree.reeId,
    files,
    reeFiles,
    ree: reeState,
    sourceRepo: ree.sourceRepo,
  };
}
