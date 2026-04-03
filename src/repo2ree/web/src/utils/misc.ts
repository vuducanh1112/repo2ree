import type { FileTreeNode, Ree, ZipEntry } from "../types";
import { buildSnapshotArchiveContent, findVirtualFileByName, listTreeFiles } from "./fileTree";
import {
  archiveWorkspacePath,
  findTreeFileBySelectedPath,
  normalizeSnapshotArchiveName,
  normalizeWorkspacePath,
} from "./paths";
import {
  REE_MANIFEST_PATH,
  REE_ROOT_PREFIX,
  REE_RUNTIME_PATH,
  REE_SBOM_PATH,
  REE_SOURCE_REPO_PREFIX,
} from "./zip";

export function triggerOnEnterOrSpace(
  event: React.KeyboardEvent<HTMLElement>,
  action: () => void,
): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

export function buildCurrentReeArchiveEntries(
  ree: Ree,
  virtualFiles: FileTreeNode[],
  sourceSnapshotFiles: FileTreeNode[],
  sourceSnapshotArchiveName?: string,
): ZipEntry[] {
  const enc = new TextEncoder();
  const entries: ZipEntry[] = [];
  const workspaceFiles = listTreeFiles(virtualFiles);
  const sourcePaths = new Set(
    listTreeFiles(sourceSnapshotFiles).map((f) => normalizeWorkspacePath(f.path)),
  );
  let runtimeIncludedInArchive = false;

  const manifest = {
    ree_version: "1.0",
    name: ree.name || null,
    origin_url: ree.origin_url || null,
    source_type: ree.source_type || null,
    runtime: ree.runtime || null,
    build_script: ree.build_runtime_script || null,
    activation_script: ree.activation_script || null,
    sbom: ree.sbom || null,
    swhid: ree.swhid || null,
    zenodo_doi: ree.zenodo_doi || null,
    dataverse_doi: ree.dataverse_doi || null,
    hardware_description: ree.hardware_description || {},
    sealed_at: ree._sealedAt || null,
    seal_hash: ree._sealHash || null,
    eval_level: ree._evalLevel ?? 0,
    source_included: !!ree._sourceIncluded,
    source_available: !!ree._sourceAvailable,
    source_acquired_by: ree._sourceAcquiredBy || null,
    source_snapshot_archive: ree._sourceSnapshotArchive || null,
    source_snapshot_captured_at: ree._sourceSnapshotCapturedAt || null,
    runtime_included: false,
  };

  if (ree.sbom && ree.sbom !== "__skipped__") {
    const sbomNode = findVirtualFileByName(virtualFiles, ree.sbom);
    const sbomContent =
      sbomNode?.content ??
      JSON.stringify({ note: "SBOM not yet generated — run Generate SBOM first" }, null, 2);
    entries.push({ path: REE_SBOM_PATH, data: enc.encode(sbomContent) });
  }

  if (ree._runtimeIncluded && ree.runtime && ree.runtime !== "__skipped__") {
    const runtimeNode = findVirtualFileByName(virtualFiles, ree.runtime);
    const runtimeContent = runtimeNode?.content;
    if (runtimeContent && runtimeContent.trim().length > 0) {
      entries.push({ path: REE_RUNTIME_PATH, data: enc.encode(runtimeContent) });
      runtimeIncludedInArchive = true;
    }
  }

  manifest.runtime_included = runtimeIncludedInArchive;
  entries.push({ path: REE_MANIFEST_PATH, data: enc.encode(JSON.stringify(manifest, null, 2)) });

  if (ree._sourceIncluded && sourceSnapshotFiles.length > 0) {
    for (const file of listTreeFiles(sourceSnapshotFiles)) {
      entries.push({
        path: `${REE_SOURCE_REPO_PREFIX}${file.path}`,
        data: enc.encode(file.content),
      });
    }

    const archiveName = normalizeSnapshotArchiveName(
      sourceSnapshotArchiveName || ree._sourceSnapshotArchive || "source-original.tar.gz",
    );
    const archiveContent = buildSnapshotArchiveContent(
      sourceSnapshotFiles,
      ree._sourceSnapshotCapturedAt,
    );
    entries.push({ path: `${REE_ROOT_PREFIX}${archiveName}`, data: enc.encode(archiveContent) });
  }

  const selectedScripts: Array<{
    key: "build_runtime_script" | "activation_script";
    path: string;
  }> = [
    { key: "build_runtime_script", path: ree.build_runtime_script || "" },
    { key: "activation_script", path: ree.activation_script || "" },
  ];

  for (const selected of selectedScripts) {
    const selectedPath = normalizeWorkspacePath(selected.path);
    if (!selectedPath) continue;
    const selectedFile = findTreeFileBySelectedPath(workspaceFiles, selectedPath);
    if (!selectedFile) continue;
    if (sourcePaths.has(normalizeWorkspacePath(selectedFile.path))) continue;
    const archivePath = archiveWorkspacePath(selectedPath);
    if (!archivePath) continue;
    const reePath = `${REE_ROOT_PREFIX}${archivePath}`;
    if (entries.some((entry) => entry.path === reePath)) continue;
    entries.push({ path: reePath, data: enc.encode(selectedFile.content || "") });
  }

  return entries;
}
