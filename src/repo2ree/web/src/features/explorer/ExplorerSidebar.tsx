import { Ic } from "../../components/Icon";
import { PAGE } from "../../constants/pages";
import { SERVICES } from "../../constants/services";
import { C, F, hoverBg, hoverColor, S_SECTION_LABEL } from "../../constants/theme";
import type { ActionStates, Badges, ExplorerPage, Ree, Service, Timestamps } from "../../types";
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
    desc: "Input metadata about the project",
  },
  {
    n: 3,
    key: PAGE.EVALUATE,
    label: "Evaluate",
    IC: Ic.star,
    svc: SERVICE_BY_KEY[PAGE.EVALUATE],
    desc: "Score reproducibility level",
  },
  {
    n: 4,
    key: PAGE.BUILD,
    label: "Build Runtime",
    IC: Ic.cpu,
    svc: SERVICE_BY_KEY[PAGE.BUILD],
    desc: "Build the runtime tarball",
  },
  {
    n: 5,
    key: PAGE.SBOM,
    label: "Generate SBOM",
    IC: Ic.package,
    svc: SERVICE_BY_KEY[PAGE.SBOM],
    desc: "Scan runtime with syft",
  },
  {
    n: 6,
    key: PAGE.ACTIVATION,
    label: "Test Activation",
    IC: Ic.shield,
    svc: SERVICE_BY_KEY[PAGE.ACTIVATION],
    desc: "Verify container activates",
  },
  {
    n: 7,
    key: PAGE.ARCHIVE,
    label: "Deposit & Share",
    IC: Ic.globe,
    svc: null,
    desc: "Archive and publish",
  },
  { n: 8, key: PAGE.SEAL, label: "Seal", IC: Ic.lock, svc: null, desc: "Seal the REE" },
];

function hasWorkflowStepRun(stepKey: ExplorerPage, ree: Ree, badges: Badges): boolean {
  if (stepKey === PAGE.SOURCE) {
    return !!ree._sourceAvailable;
  }
  if (stepKey === PAGE.METADATA) {
    return !!ree.name;
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
  actionStates: ActionStates;
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
  actionStates,
  badges,
  timestamps,
  setPage,
  setNavCollapsed,
  onDownloadRee,
  onPreviewReviewer,
}: ExplorerSidebarProps) {
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
          padding: navCollapsed ? "8px 6px 4px" : "8px 8px 4px",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        {iconBtn(PAGE.OVERVIEW, Ic.layers(12), "Overview", "pod · level · state")}
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
        <div style={{ padding: "10px 14px 4px" }}>
          <span style={{ ...S_SECTION_LABEL, fontSize: 10, letterSpacing: 1.3 }}>Workflow</span>
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
          const isRunning = !!step.svc && actionStates[step.key] === "loading";
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
                  {isRunning ? (
                    <span
                      style={{
                        display: "flex",
                        color: C.accent,
                        animation: "spin 0.9s linear infinite",
                      }}
                    >
                      {Ic.loader(11)}
                    </span>
                  ) : (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        fontFamily: F.mono,
                        color: isActive ? "#fff" : C.textMuted,
                      }}
                    >
                      {step.n}
                    </span>
                  )}
                  {hasRun && !isRunning && !isActive && (
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
                      {isRunning ? "running…" : tsShort ? `last run ${tsShort}` : step.desc}
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
                    background: C.border,
                    borderRadius: 99,
                    marginTop: 1,
                    marginBottom: 1,
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
            subtitle="export capsule.zip"
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
