import type { Badges, Timestamps } from "../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import { C, F, S_SECTION_LABEL } from "../../theme/theme";
import { NavEntryButton } from "../AppShellNav";
import { type AppShellPage, isRuntimeEnvPage, PAGE } from "../state/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "./processSteps";

interface LifecycleNavProps {
  page: AppShellPage;
  ree: ReeEditorViewModel;
  badges: Badges;
  timestamps: Timestamps;
  navCollapsed: boolean;
  provisioned: boolean;
  setPage: (page: AppShellPage) => void;
}

export function LifecycleNav({
  page,
  ree,
  badges,
  timestamps,
  navCollapsed,
  provisioned,
  setPage,
}: LifecycleNavProps) {
  const completedCount = PROCESS_STEPS.filter((step) =>
    resolveNavCompleted(step, ree, badges, provisioned),
  ).length;

  return (
    <>
      {!navCollapsed && (
        <div style={{ padding: "10px 14px 4px", display: "flex", justifyContent: "space-between" }}>
          <span style={{ ...S_SECTION_LABEL, fontSize: 10, letterSpacing: 1.3 }}>Lifecycle</span>
          <span
            style={{
              fontSize: 10,
              color: C.textMuted,
              fontFamily: F.mono,
              letterSpacing: 0.3,
            }}
          >
            {completedCount}/{PROCESS_STEPS.length}
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
        {PROCESS_STEPS.map((step, index) => {
          const isActive = page === step.key || (step.key === PAGE.BUILD && isRuntimeEnvPage(page));
          const hasRun = resolveNavCompleted(step, ree, badges, provisioned);
          const timestamp = resolveStepTimestamp(step.key, timestamps);
          const tsShort = timestamp
            ? new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            : null;
          const isLast = index === PROCESS_STEPS.length - 1;
          const locked = !provisioned && step.key !== PAGE.WORKBENCH;

          return (
            <div
              key={step.key}
              style={{ display: "flex", flexDirection: "column", opacity: locked ? 0.4 : 1 }}
            >
              <NavEntryButton
                title={
                  navCollapsed
                    ? `${step.n}. ${step.label}${tsShort ? ` — last run ${tsShort}` : ""}`
                    : undefined
                }
                onClick={() => {
                  if (!locked) setPage(step.key);
                }}
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
                  <span style={{ display: "flex", color: isActive ? "#fff" : C.textMuted }}>
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
    </>
  );
}

function resolveStepTimestamp(stepKey: AppShellPage, timestamps: Timestamps): string | undefined {
  if (stepKey !== PAGE.BUILD) {
    return timestamps[stepKey];
  }

  return [timestamps.build, timestamps.sbom, timestamps.activation]
    .filter((value): value is string => !!value)
    .sort()
    .at(-1);
}
