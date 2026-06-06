import { Ic } from "../../shared/components/Icon";
import { C } from "../../theme/theme";
import { ActionBtn } from "../AppShellNav";

interface SidebarFooterProps {
  navCollapsed: boolean;
  onPreviewReviewer: () => void;
}

export function SidebarFooter({ navCollapsed, onPreviewReviewer }: SidebarFooterProps) {
  return (
    <div
      style={{
        marginTop: "auto",
        padding: navCollapsed ? "8px 6px" : "8px 8px",
        borderTop: `1px solid ${C.border}`,
      }}
    >
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
