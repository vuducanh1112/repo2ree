import { useMemo, useState } from "react";
import type { ReeFile } from "../../../../../core/ree/ReeTypes";
import { Ic } from "../../../shared/components/Icon";
import { lgPageColors } from "../../../theme/lightGlassTheme";
import { S_WORKFLOW_PAGE_BODY, S_WORKFLOW_SERVICE_ROOT } from "../../../theme/theme";
import { AssemblyPageHeader } from "../../components/pageChrome";
import { FilesEmptyState } from "./FilesEmptyState";
import { FilesTreePane } from "./FilesTreePane";
import { FileViewer } from "./FileViewer";
import { buildReeFileTree, flattenTreeWithPaths } from "./filesPageHelpers";

const WORKSPACE_PREFIX = "workspace/";

interface PageFilesProps {
  reeFiles: ReeFile[];
  onDownloadWorkspaceFile?: (path: string, suggestedName?: string) => Promise<void>;
}

export function PageFiles({ reeFiles, onDownloadWorkspaceFile }: PageFilesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const reeFileTree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  const reeFlatEntries = useMemo(() => flattenTreeWithPaths(reeFileTree), [reeFileTree]);

  const selectedReeEntry = selectedId
    ? reeFlatEntries.find((entry) => entry.node.id === selectedId) || null
    : null;
  const selectedFile = selectedReeEntry?.node || null;
  const selectedPath = selectedReeEntry?.path || null;

  const workspaceDownloadPath = selectedPath?.startsWith(WORKSPACE_PREFIX)
    ? selectedPath.slice(WORKSPACE_PREFIX.length)
    : null;

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <AssemblyPageHeader
        color={lgPageColors.files}
        icon={Ic.files(18)}
        title="Files"
        subtitle="Inspect the on-disk REE layout"
        tips={[
          "The tree mirrors the REE directory: manifest, snapshot, upstream/, overlay/, artifacts/, workspace/.",
          "Run lifecycle steps to generate or update REE files.",
        ]}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <FilesTreePane
          reeFileCount={reeFiles.length}
          reeFileTree={reeFileTree}
          selectedId={selectedId}
          onSelect={setSelectedId}
          hasSelection={!!selectedFile}
        />

        {selectedFile ? (
          <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
            <FileViewer
              file={selectedFile}
              path={selectedPath}
              onClose={() => setSelectedId(null)}
              label="ree"
              onDownload={
                workspaceDownloadPath && onDownloadWorkspaceFile
                  ? () => onDownloadWorkspaceFile(workspaceDownloadPath, selectedFile.name)
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
