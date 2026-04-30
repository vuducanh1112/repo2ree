import { Ic } from "../../shared/components/Icon";
import { C } from "../../theme/theme";
import { ActionBtn } from "../WorkspaceShellNav";

interface SidebarFooterProps {
  navCollapsed: boolean;
  onDownloadRee: () => void;
  onPreviewReviewer: () => void;
}

export function SidebarFooter({
  navCollapsed,
  onDownloadRee,
  onPreviewReviewer,
}: SidebarFooterProps) {
  return (
    <div
      style={{
        marginTop: "auto",
        padding: navCollapsed ? "8px 6px" : "8px 8px",
        borderTop: `1px solid ${C.border}`,
      }}
    >
      <div style={{ marginBottom: 8 }}>
        <ActionBtn
          title="Download REE"
          label="Download REE"
          subtitle="export backend archive"
          icon={Ic.download(11)}
          iconBg="#2563eb"
          labelColor="#1e3a8a"
          subtitleColor={C.textMuted}
          background="#eef6ff"
          border="#dbeafe"
          hoverBackground="#e0f2ff"
          hoverBorder="#93c5fd"
          navCollapsed={navCollapsed}
          onClick={onDownloadRee}
        />
      </div>
      <ActionBtn
        title="Preview Review"
        label="Preview"
        subtitle="reviewer's view"
        icon={Ic.star(11)}
        iconBg="#f59e0b"
        labelColor="#92400e"
        subtitleColor="#b45309"
        background="#fef3c7"
        border="#fde68a"
        hoverBackground="#fef08a40"
        hoverBorder="#f59e0b"
        navCollapsed={navCollapsed}
        onClick={onPreviewReviewer}
      />
    </div>
  );
}
