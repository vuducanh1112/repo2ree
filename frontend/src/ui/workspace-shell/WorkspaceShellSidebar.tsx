import {
  PAGE,
  type WorkspaceShellPage,
} from "../../application/workspace-shell/WorkspaceShellPages";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import type { Badges, Timestamps } from "../../domain/ree/ReeTypes";
import { LEVELS } from "../../domain/review/levels";
import { Ic } from "../shared/components/Icon";
import { C, hoverBg, hoverColor } from "../theme/theme";
import { getPodCableStates } from "./pages/overview/podCableState";
import { LifecycleNav } from "./sidebar/LifecycleNav";
import { OverviewCard } from "./sidebar/OverviewCard";
import { SidebarFooter } from "./sidebar/SidebarFooter";
import { NavEntryButton } from "./WorkspaceShellNav";

interface WorkspaceShellSidebarProps {
  page: WorkspaceShellPage;
  ree: ReeDraftViewModel;
  navCollapsed: boolean;
  badges: Badges;
  timestamps: Timestamps;
  setPage: (page: WorkspaceShellPage) => void;
  setNavCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  onDownloadRee: () => void;
  onPreviewReviewer: () => void;
}

export function WorkspaceShellSidebar({
  page,
  ree,
  navCollapsed,
  badges,
  timestamps,
  setPage,
  setNavCollapsed,
  onDownloadRee,
  onPreviewReviewer,
}: WorkspaceShellSidebarProps) {
  const level = Math.min(ree.evalLevel ?? 0, LEVELS.length - 1);
  const levelMeta = LEVELS[level];
  const cableStates = getPodCableStates(ree, badges);
  const leftCables = cableStates
    .filter((cable) => cable.podSide === "left")
    .sort((first, second) => first.podRank - second.podRank);
  const rightCables = cableStates
    .filter((cable) => cable.podSide === "right")
    .sort((first, second) => first.podRank - second.podRank);
  const topCable = cableStates.find((cable) => cable.podSide === "top") || null;

  return (
    <nav
      style={{
        width: navCollapsed ? 52 : 200,
        borderRight: `1px solid ${C.border}`,
        background: C.surface,
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
        overflowX: "hidden",
        flexShrink: 0,
        minHeight: 0,
        transition: "width 0.2s cubic-bezier(0.4,0,0.2,1)",
      }}
    >
      <div
        style={{
          padding: "6px 8px",
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          justifyContent: navCollapsed ? "center" : "flex-start",
        }}
      >
        <button
          type="button"
          onClick={() => setNavCollapsed((collapsed) => !collapsed)}
          title={navCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 30,
            height: 30,
            borderRadius: 6,
            background: "transparent",
            border: "none",
            cursor: "pointer",
            color: C.textMuted,
            transition: "all 0.12s",
            flexShrink: 0,
          }}
          {...hoverBg(C.surfaceAlt, "transparent")}
          {...hoverColor(C.textMid, C.textMuted)}
        >
          {Ic.menu(15)}
        </button>
      </div>

      <OverviewCard
        navCollapsed={navCollapsed}
        page={page}
        level={level}
        levelMeta={levelMeta}
        cableStates={cableStates}
        leftCables={leftCables}
        rightCables={rightCables}
        topCable={topCable}
        setPage={setPage}
      />

      <div
        style={{
          padding: navCollapsed ? "4px 6px 8px" : "4px 8px 8px",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <NavEntryButton
          title={navCollapsed ? "Browse Files" : undefined}
          onClick={() => setPage(PAGE.FILES)}
          isActive={page === PAGE.FILES}
          navCollapsed={navCollapsed}
        >
          <div
            style={{
              width: 22,
              height: 22,
              borderRadius: 6,
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: page === PAGE.FILES ? C.accent : C.surfaceAlt,
              border: page === PAGE.FILES ? "none" : `1.5px solid ${C.border}`,
            }}
          >
            <span style={{ display: "flex", color: page === PAGE.FILES ? "#fff" : C.textMuted }}>
              {Ic.files(12)}
            </span>
          </div>
          {!navCollapsed && <div style={{ color: C.textMid, fontSize: 13 }}>Browse Files</div>}
        </NavEntryButton>
      </div>

      <LifecycleNav
        page={page}
        ree={ree}
        badges={badges}
        timestamps={timestamps}
        navCollapsed={navCollapsed}
        setPage={setPage}
      />

      <SidebarFooter
        navCollapsed={navCollapsed}
        onDownloadRee={onDownloadRee}
        onPreviewReviewer={onPreviewReviewer}
      />
    </nav>
  );
}
