import { useMemo, useState } from "react";
import type { ReeFile } from "../../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { S_WORKFLOW_PAGE_BODY, S_WORKFLOW_SERVICE_ROOT } from "../../../theme/theme";
import { AssemblyPageHeader } from "../../components/pageChrome";
import { FilesEmptyState } from "./FilesEmptyState";
import { FilesTreePane } from "./FilesTreePane";
import { FileViewer } from "./FileViewer";
import { buildReeFileTree, flattenTree, flattenTreeWithPaths } from "./filesPageHelpers";

interface PageFilesProps {
  files: FileTreeNode[];
  reeFiles: ReeFile[];
  onDownloadWorkspaceFile?: (path: string, suggestedName?: string) => Promise<void>;
}

export function PageFiles({ files, reeFiles, onDownloadWorkspaceFile }: PageFilesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sourceFiles = files || [];
  const reeFileTree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  const sourceFlatEntries = useMemo(() => flattenTreeWithPaths(sourceFiles), [sourceFiles]);
  const reeFlatEntries = useMemo(() => flattenTreeWithPaths(reeFileTree), [reeFileTree]);
  const reeFlatFiles = useMemo(() => flattenTree(reeFileTree), [reeFileTree]);

  const selectedSourceEntry = selectedId
    ? sourceFlatEntries.find((entry) => entry.node.id === selectedId) || null
    : null;
  const selectedReeEntry = selectedId
    ? reeFlatEntries.find((entry) => entry.node.id === selectedId) || null
    : null;
  const selectedFile = selectedSourceEntry?.node || selectedReeEntry?.node || null;

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <AssemblyPageHeader
        color="#6366f1"
        icon={Ic.files(18)}
        title="Files"
        subtitle="Inspect workspace inputs and generated REE files side by side"
        tips={[
          "Use this view to verify paths referenced by source, runtime, scripts, and SBOM fields.",
          "Workspace is read-only here; run lifecycle steps to generate or update REE files.",
        ]}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <FilesTreePane
          sourceFiles={sourceFiles}
          reeFiles={reeFiles}
          reeFileTree={reeFileTree}
          selectedId={selectedId}
          onSelect={setSelectedId}
          hasSelection={!!selectedFile}
        />

        {selectedFile ? (
          <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
            <FileViewer
              file={selectedFile}
              onClose={() => setSelectedId(null)}
              label={reeFlatFiles.find((f) => f.id === selectedId) ? "ree" : "workspace"}
              onDownload={
                selectedSourceEntry?.path && onDownloadWorkspaceFile
                  ? () => onDownloadWorkspaceFile(selectedSourceEntry.path, selectedFile.name)
                  : undefined
              }
            />
          </div>
        ) : (
          <FilesEmptyState />
        )}
      </div>
    </div>
  );
}
