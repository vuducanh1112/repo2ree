import type { ReeProject, WorkspaceResetPayload } from "../../application/ports/repositoryTypes";
import type { WorkspaceRepository } from "../../application/ports/WorkspaceRepository";
import type { Ree } from "../../domain/ree/ReeSpec";
import type { ReeFile } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceDetailDto } from "../api";
import { mapWorkspaceDraftToRee } from "../api/ReeDtoMappers";
import type { HttpRepositoryClient } from "./HttpRepositoryClient";

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

function mapWorkspace(workspace: WorkspaceDetailDto): ReeProject<FileTreeNode> {
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
  const ree: Ree = mapWorkspaceDraftToRee(workspace);

  return {
    id: workspace.reeId,
    files,
    reeFiles,
    ree,
  };
}

export function createHttpWorkspaceRepository(
  repositoryClient: HttpRepositoryClient,
): WorkspaceRepository<FileTreeNode> {
  return {
    async getWorkspace(id) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      const workspace = await repositoryClient.workspaceApi.getWorkspace(workspaceId);
      return mapWorkspace(workspace);
    },
    async updateFile(id, path, content) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      await repositoryClient.workspaceApi.putFileContent(workspaceId, { path, content });
    },
    async updateReeDraft(id, reePatch) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      await repositoryClient.workspaceApi.patchWorkspace(workspaceId, { reePatch });
    },
    async deleteFile(id, path) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      await repositoryClient.workspaceApi.deleteFileContent(workspaceId, path);
    },
    async getFileBytes(id, path) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      return repositoryClient.workspaceApi.getFileBytes(workspaceId, path);
    },
    async resetWorkspaceRequest(id, request: WorkspaceResetPayload) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      const mode = request.mode || "clear";
      if (mode === "clear") {
        await repositoryClient.workspaceApi.removeSource(workspaceId);
        return;
      }
      if (mode === "download") {
        await repositoryClient.workspaceApi.acquireSource(workspaceId, {
          originUrl: String(request.source ?? ""),
          sourceType: String(request.sourceType ?? "git") as "git" | "tarball" | "zip",
        });
        return;
      }
      if (mode === "upload") {
        const archiveName = String(request.archiveName || "source.tar.gz");
        const init = await repositoryClient.workspaceApi.initUpload(workspaceId, {
          fileName: archiveName,
          size: 0,
          contentType: "application/gzip",
        });
        if (request.archiveContentBase64) {
          const archiveData = decodeBase64ToArrayBuffer(String(request.archiveContentBase64));
          await repositoryClient.workspaceApi.uploadSourceBytes(init.uploadUrl, archiveData);
        }
        await repositoryClient.workspaceApi.completeUpload(
          workspaceId,
          init.uploadToken,
          archiveName,
        );
        return;
      }
      throw new Error(`Unsupported workspace reset mode: ${mode}`);
    },
  };
}

function decodeBase64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}
