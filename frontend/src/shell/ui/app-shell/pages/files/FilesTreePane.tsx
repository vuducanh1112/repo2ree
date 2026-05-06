import type { ReeFile } from "../../../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import { FileNode } from "../../../shared/components/FileTree";
import { C, F, S_SECTION_LABEL } from "../../../theme/theme";

interface SectionHeaderProps {
  label: string;
  badge?: string;
  color: string;
}

function SectionHeader({ label, badge, color }: SectionHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "7px 10px 5px",
        position: "sticky",
        top: 0,
        background: C.surface,
        zIndex: 1,
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <div style={{ width: 3, height: 12, borderRadius: 99, background: color, flexShrink: 0 }} />
      <span
        style={{
          ...S_SECTION_LABEL,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: 1.3,
          color: C.textMid,
          flex: 1,
        }}
      >
        {label}
      </span>
      {badge && (
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            color: C.textMuted,
            background: C.surfaceAlt,
            border: `1px solid ${C.border}`,
            borderRadius: 3,
            padding: "1px 5px",
            fontFamily: F.sans,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  );
}

interface FilesTreePaneProps {
  sourceFiles: FileTreeNode[];
  reeFiles: ReeFile[];
  reeFileTree: FileTreeNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  hasSelection: boolean;
}

export function FilesTreePane({
  sourceFiles,
  reeFiles,
  reeFileTree,
  selectedId,
  onSelect,
  hasSelection,
}: FilesTreePaneProps) {
  return (
    <div
      style={{
        width: hasSelection ? 200 : 280,
        borderRight: `1px solid ${C.border}`,
        background: C.surface,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
        transition: "width 0.18s",
      }}
    >
      <div style={{ overflowY: "auto", flex: 1 }}>
        <SectionHeader label="Workspace" badge="read-only" color="#f59e0b" />
        <div style={{ padding: "4px 4px 8px" }}>
          {sourceFiles.map((sourceNode) => (
            <FileNode
              key={sourceNode.id}
              node={sourceNode}
              onSelect={(selectedNode) => onSelect(selectedNode.id)}
              selectedId={selectedId}
            />
          ))}
        </div>

        <SectionHeader
          label="REE Files"
          badge={`${reeFiles.length} file${reeFiles.length !== 1 ? "s" : ""}`}
          color="#7c3aed"
        />
        <div style={{ padding: "4px 4px 8px" }}>
          {reeFiles.length === 0 ? (
            <div
              style={{
                padding: "10px 12px",
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
                fontStyle: "italic",
              }}
            >
              Run Create &amp; Build to generate files
            </div>
          ) : (
            reeFileTree.map((reeNode) => (
              <FileNode
                key={reeNode.id}
                node={reeNode}
                onSelect={(selectedNode) => onSelect(selectedNode.id)}
                selectedId={selectedId}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
