import { Ic } from "../../components/Icon";
import { LEVELS } from "../../constants/levels";
import { PAGE } from "../../constants/pages";
import { SERVICES } from "../../constants/services";
import { C, F, hoverBg, hoverColor, S_SECTION_LABEL } from "../../constants/theme";
import type { Badges, ExplorerPage, Ree, Service, Timestamps } from "../../types";
import { hbomHasAnyComponents } from "../../utils/hbom";
import { PodWidget } from "../overview/PodWidget";
import { getPodCableStates } from "../overview/podCableState";
import { ActionBtn, NavEntryButton } from "./ExplorerNav";

interface WorkflowStep {
  n: number;
  key: ExplorerPage;
  label: string;
  IC: (size?: number) => JSX.Element;
  svc: Service | null;
  desc: string;
}

const SERVICE_BY_KEY: Record<string, Service> = Object.fromEntries(
  SERVICES.map((service) => [service.key, service]),
) as Record<string, Service>;

const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    n: 1,
    key: PAGE.SOURCE,
    label: "Source Repo",
    IC: Ic.globe,
    svc: null,
    desc: "Set origin, type, and download source files",
  },
  {
    n: 2,
    key: PAGE.METADATA,
    label: "Provide Metadata",
    IC: Ic.grid,
    svc: null,
    desc: "Input project identity metadata",
  },
  {
    n: 3,
    key: PAGE.HBOM,
    label: "Create HBOM",
    IC: Ic.chip,
    svc: null,
    desc: "Enter hardware bill of materials",
  },
  {
    n: 4,
    key: PAGE.EVALUATE,
    label: "Evaluate",
    IC: Ic.star,
    svc: SERVICE_BY_KEY[PAGE.EVALUATE],
    desc: "Score reproducibility level",
  },
  {
    n: 5,
    key: PAGE.BUILD,
    label: "Build Runtime",
    IC: Ic.cpu,
    svc: SERVICE_BY_KEY[PAGE.BUILD],
    desc: "Build the runtime tarball",
  },
  {
    n: 6,
    key: PAGE.SBOM,
    label: "Generate SBOM",
    IC: Ic.package,
    svc: SERVICE_BY_KEY[PAGE.SBOM],
    desc: "Scan runtime with syft",
  },
  {
    n: 7,
    key: PAGE.ACTIVATION,
    label: "Test Activation",
    IC: Ic.shield,
    svc: SERVICE_BY_KEY[PAGE.ACTIVATION],
    desc: "Verify container activates",
  },
  {
    n: 8,
    key: PAGE.ARCHIVE,
    label: "Deposit & Share",
    IC: Ic.globe,
    svc: null,
    desc: "Archive and publish",
  },
  { n: 9, key: PAGE.SEAL, label: "Seal", IC: Ic.lock, svc: null, desc: "Seal the REE" },
];

function hasWorkflowStepRun(stepKey: ExplorerPage, ree: Ree, badges: Badges): boolean {
  if (stepKey === PAGE.SOURCE) {
    return !!ree._sourceAvailable;
  }
  if (stepKey === PAGE.METADATA) {
    return !!ree.name;
  }
  if (stepKey === PAGE.HBOM) {
    return hbomHasAnyComponents(ree.hardware_description);
  }
  if (stepKey === PAGE.SEAL) {
    return !!ree._sealedAt;
  }
  if (stepKey === PAGE.ARCHIVE) {
    return !!badges?.swh || !!badges?.zenodo || !!badges?.dataverse;
  }
  return !!badges?.[stepKey];
}

interface ExplorerSidebarProps {
  page: ExplorerPage;
  ree: Ree;
  navCollapsed: boolean;
  badges: Badges;
  timestamps: Timestamps;
  setPage: (page: ExplorerPage) => void;
  setNavCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  onDownloadRee: () => void;
  onPreviewReviewer: () => void;
}

export function ExplorerSidebar({
  page,
  ree,
  navCollapsed,
  badges,
  timestamps,
  setPage,
  setNavCollapsed,
  onDownloadRee,
  onPreviewReviewer,
}: ExplorerSidebarProps) {
  const level = Math.min(ree._evalLevel ?? 0, LEVELS.length - 1);
  const levelMeta = LEVELS[level];
  const isOverviewActive = page === PAGE.OVERVIEW;

  const cableStates = getPodCableStates(ree, badges);
  const leftCables = cableStates
    .filter((cable) => cable.podSide === "left")
    .sort((firstCable, secondCable) => firstCable.podRank - secondCable.podRank);
  const rightCables = cableStates
    .filter((cable) => cable.podSide === "right")
    .sort((firstCable, secondCable) => firstCable.podRank - secondCable.podRank);
  const topCable = cableStates.find((cable) => cable.podSide === "top") || null;

  const iconBtn = (
    key: ExplorerPage,
    icon: React.ReactNode,
    label: string,
    subtitle?: string | null,
  ) => {
    const isActive = page === key;
    return (
      <NavEntryButton
        title={navCollapsed ? label : undefined}
        onClick={() => setPage(key)}
        isActive={isActive}
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
            background: isActive ? C.accent : C.surfaceAlt,
            border: isActive ? "none" : `1.5px solid ${C.border}`,
          }}
        >
          <span style={{ display: "flex", color: isActive ? "#fff" : C.textMuted }}>{icon}</span>
        </div>
        {!navCollapsed && (
          <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
            <div
              style={{
                fontSize: 13,
                fontFamily: F.sans,
                fontWeight: 600,
                color: isActive ? C.accent : C.textMid,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {label}
            </div>
            {subtitle && (
              <div
                style={{
                  fontSize: 10,
                  color: C.textMuted,
                  fontFamily: F.sans,
                  marginTop: 1,
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
        )}
      </NavEntryButton>
    );
  };

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

      <div
        style={{
          padding: navCollapsed ? "8px 4px 8px" : "8px 8px 10px",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <button
          type="button"
          title={navCollapsed ? "Overview" : undefined}
          onClick={() => setPage(PAGE.OVERVIEW)}
          style={{
            width: "100%",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            padding: navCollapsed ? "6px 0" : "4px 2px 2px",
            borderRadius: 10,
          }}
          {...hoverBg(C.surfaceAlt, "transparent")}
        >
          {navCollapsed ? (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                minHeight: 40,
              }}
            >
              <PodWidget level={level} size={40} compact />
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    fontWeight: 700,
                    color: isOverviewActive ? C.accent : C.text,
                    letterSpacing: 0.2,
                  }}
                >
                  REE
                </div>
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: F.mono,
                    color: levelMeta.ink,
                    background: levelMeta.bg,
                    border: `1px solid ${levelMeta.color}44`,
                    borderRadius: 99,
                    padding: "1px 6px",
                  }}
                >
                  L{level}
                </span>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto 1fr",
                  alignItems: "center",
                  gap: 6,
                  borderRadius: 10,
                  padding: "6px 6px",
                  background: isOverviewActive ? `${levelMeta.color}08` : "transparent",
                  outline: isOverviewActive
                    ? `1px solid ${levelMeta.color}44`
                    : "1px solid transparent",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {leftCables.map((cable) => {
                    const on = cable.connected;
                    return (
                      <div
                        key={cable.id}
                        style={{
                          display: "flex",
                          justifyContent: "flex-end",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <span
                          style={{
                            width: 28,
                            height: 2,
                            borderRadius: 99,
                            background: on ? cable.color : C.border,
                            opacity: on ? 0.9 : 0.55,
                            boxShadow: on ? `0 0 7px ${cable.color}55` : "none",
                          }}
                        />
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: on ? cable.color : C.borderMid,
                            boxShadow: on ? `0 0 8px ${cable.color}88` : "none",
                          }}
                        />
                      </div>
                    );
                  })}
                </div>

                <PodWidget level={level} size={66} compact />

                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {rightCables.map((cable) => {
                    const on = cable.connected;
                    return (
                      <div
                        key={cable.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: on ? cable.color : C.borderMid,
                            boxShadow: on ? `0 0 8px ${cable.color}88` : "none",
                          }}
                        />
                        <span
                          style={{
                            width: 28,
                            height: 2,
                            borderRadius: 99,
                            background: on ? cable.color : C.border,
                            opacity: on ? 0.9 : 0.55,
                            boxShadow: on ? `0 0 7px ${cable.color}55` : "none",
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>

              {topCable && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    marginTop: -2,
                    marginBottom: 2,
                  }}
                >
                  <span
                    style={{
                      width: 2,
                      height: 10,
                      borderRadius: 99,
                      background: topCable.connected ? topCable.color : C.border,
                      opacity: topCable.connected ? 0.95 : 0.55,
                      boxShadow: topCable.connected ? `0 0 7px ${topCable.color}55` : "none",
                    }}
                  />
                </div>
              )}

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                  gap: 6,
                }}
              >
                {cableStates.map((cable) => {
                  const on = cable.connected;
                  return (
                    <div
                      key={cable.id}
                      style={{
                        fontSize: 9,
                        color: on ? C.textMid : C.textMuted,
                        fontFamily: F.mono,
                        textAlign: "center",
                        opacity: on ? 0.95 : 0.75,
                      }}
                    >
                      {cable.connected ? "✓" : "·"} {cable.label}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </button>
      </div>

      <div
        style={{
          padding: navCollapsed ? "4px 6px 8px" : "4px 8px 8px",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        {iconBtn(PAGE.FILES, Ic.files(12), "Browse Files", null)}
      </div>

      {!navCollapsed && (
        <div style={{ padding: "10px 14px 4px", display: "flex", justifyContent: "space-between" }}>
          <span style={{ ...S_SECTION_LABEL, fontSize: 10, letterSpacing: 1.3 }}>Workflow</span>
          <span
            style={{
              fontSize: 10,
              color: C.textMuted,
              fontFamily: F.mono,
              letterSpacing: 0.3,
            }}
          >
            {WORKFLOW_STEPS.filter((step) => hasWorkflowStepRun(step.key, ree, badges)).length}/
            {WORKFLOW_STEPS.length}
          </span>
        </div>
      )}
      {navCollapsed && <div style={{ height: 8 }} />}

      <div
        style={{
          padding: navCollapsed ? "0 6px" : "0 8px",
          display: "flex",
          flexDirection: "column",
          gap: 1,
          flex: 1,
        }}
      >
        {WORKFLOW_STEPS.map((step, index) => {
          const isActive = page === step.key;
          const hasRun = hasWorkflowStepRun(step.key, ree, badges);
          const timestamp = timestamps[step.key];
          const tsShort = timestamp
            ? new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            : null;
          const isLast = index === WORKFLOW_STEPS.length - 1;

          return (
            <div key={step.key} style={{ display: "flex", flexDirection: "column" }}>
              <NavEntryButton
                title={
                  navCollapsed
                    ? `${step.n}. ${step.label}${tsShort ? ` — last run ${tsShort}` : ""}`
                    : undefined
                }
                onClick={() => setPage(step.key)}
                isActive={isActive}
                navCollapsed={navCollapsed}
              >
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: isActive ? C.accent : C.surfaceAlt,
                    border: isActive ? "none" : `1.5px solid ${hasRun ? C.accentBorder : C.border}`,
                    position: "relative",
                    transition: "all 0.2s",
                  }}
                >
                  <span
                    style={{
                      display: "flex",
                      color: isActive ? "#fff" : C.textMuted,
                    }}
                  >
                    {step.IC(12)}
                  </span>
                  {hasRun && !isActive && (
                    <div
                      style={{
                        position: "absolute",
                        bottom: -1,
                        right: -1,
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: C.accent,
                        border: `1.5px solid ${C.surface}`,
                      }}
                    />
                  )}
                </div>

                {!navCollapsed && (
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontFamily: F.sans,
                        fontWeight: isActive ? 600 : 400,
                        color: isActive ? C.accent : C.textMid,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        lineHeight: 1.3,
                      }}
                    >
                      {step.label}
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: C.textMuted,
                        fontFamily: F.mono,
                        marginTop: 1,
                      }}
                    >
                      {tsShort ? `last run ${tsShort}` : step.desc}
                    </div>
                  </div>
                )}
              </NavEntryButton>

              {!isLast && (
                <div
                  style={{
                    marginLeft: navCollapsed ? 14 : 19,
                    width: 2,
                    height: 6,
                    background: hasRun ? C.accentBorder : C.border,
                    borderRadius: 99,
                    marginTop: 1,
                    marginBottom: 1,
                    opacity: hasRun ? 0.85 : 0.6,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

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
          title="Preview as Reviewer"
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
    </nav>
  );
}
