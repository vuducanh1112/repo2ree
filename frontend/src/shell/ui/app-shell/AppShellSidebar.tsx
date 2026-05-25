import type { Badges, Timestamps } from "../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import { standingMeta } from "../../../core/review/axes";
import { Ic } from "../shared/components/Icon";
import { C, hoverBg, hoverColor } from "../theme/theme";
import { NavEntryButton } from "./AppShellNav";
import { getPodCableStates } from "./pages/overview/podCableState";
import { LifecycleNav } from "./sidebar/LifecycleNav";
import { OverviewCard } from "./sidebar/OverviewCard";
import { SidebarFooter } from "./sidebar/SidebarFooter";
import { type AppShellPage, PAGE } from "./state/pages";

interface AppShellSidebarProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  navCollapsed: boolean;
  badges: Badges;
  timestamps: Timestamps;
  setPage: (page: AppShellPage) => void;
  setNavCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  onDownloadRee: () => void;
  onPreviewReviewer: () => void;
}

export function AppShellSidebar({
  page,
  ree,
  navCollapsed,
  badges,
  timestamps,
  setPage,
  setNavCollapsed,
  onDownloadRee,
  onPreviewReviewer,
}: AppShellSidebarProps) {
  const evaluation = {
    dependencyLevel: ree.dependencyLevel ?? 0,
    environmentLevel: ree.environmentLevel ?? 0,
    machineLevel: ree.machineLevel ?? 0,
  };
  const levelMeta = standingMeta(evaluation);
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
        evaluation={evaluation}
        navCollapsed={navCollapsed}
        page={page}
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
