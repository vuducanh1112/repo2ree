import type { ReeFile } from "../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { ReeProject } from "../../domain/workspace/WorkspaceTypes";
import type { WorkspaceDetailDto } from "../../infra/api/apiTypes";
import { mapWorkspaceDetailToRee } from "../../infra/api/ReeDtoMappers";

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

export function mapWorkspaceDetailToReeProject(
  workspace: WorkspaceDetailDto,
): ReeProject<FileTreeNode> {
  const files: FileTreeNode[] = [];
  for (const file of workspace.files || []) {
    if (!file.path) {
      continue;
    }
    upsertTreeFile(files, file.path, file.content, file.size, file.kind);
  }

  const reeFiles: ReeFile[] = (workspace.reeFiles || []).map((file, index) => ({
    id: `remote-ree-${index}-${file.path}`,
    name: file.path,
    type: "file",
    tag: file.tag || "REE",
    content: file.content,
    size: file.size,
  }));
  const ree: ReeViewState = mapWorkspaceDetailToRee(workspace);

  return {
    id: workspace.reeId,
    files,
    reeFiles,
    ree,
  };
}
