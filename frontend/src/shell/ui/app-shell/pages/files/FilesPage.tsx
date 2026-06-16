import { useState } from "react";
import type { ReeFile } from "../../../../../core/ree/ReeTypes";
import { Ic } from "../../../shared/components/Icon";
import { lgPageColors } from "../../../theme/lightGlassTheme";
import { S_WORKFLOW_PAGE_BODY, S_WORKFLOW_SERVICE_ROOT } from "../../../theme/theme";
import { AssemblyPageHeader } from "../../components/pageChrome";
import { FilesEmptyState } from "./FilesEmptyState";
import { FilesTreePane } from "./FilesTreePane";
import { FileViewer } from "./FileViewer";
import { useReeFileTree } from "./useReeFileTree";

interface PageFilesProps {
  reeFiles: ReeFile[];
}

export function PageFiles({ reeFiles }: PageFilesProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { tree: reeFileTree, entryById } = useReeFileTree(reeFiles);

  const selectedFile = (selectedId ? entryById.get(selectedId)?.node : undefined) ?? null;

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
            <FileViewer file={selectedFile} />
          </div>
        ) : (
          <FilesEmptyState />
        )}
      </div>
    </div>
  );
}
