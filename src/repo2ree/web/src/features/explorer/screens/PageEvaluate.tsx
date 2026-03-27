import { useState } from "react";
import { Ic } from "../../../components/Icon";
import { LevelBadge } from "../../../components/LevelBadge";
import { LEVELS } from "../../../constants/levels";
import {
  C,
  F,
  S_FIELD_HELP_TEXT_SMALL,
  S_SECTION_LABEL,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../constants/theme";
import { MOCK_FILES } from "../../../services/dummyWorkspaceService";
import { scanDependencies } from "../../dependencies/dependencyParser";
import { LogPanel } from "../components/inputs/logPanel";
import {
  descToTwoTierTips,
  FieldRow,
  FieldSection,
  FieldTipsSidebar,
} from "../components/workflow/fieldTips";
import {
  NextStepNudge,
  RequirementsBanner,
  WorkflowPageHeader,
} from "../components/workflow/pageChrome";
import { DependencyPanel, ServiceActionSection } from "../components/workflow/servicePanels";
import type { ServicePageProps } from "./sharedWorkflowUi";

export function PageEvaluate({
  svc,
  ree,
  badges,
  virtualFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGo,
  onGoFields,
  missing,
  params,
}: ServicePageProps) {
  const files = virtualFiles;

  const depGroups = scanDependencies(files || MOCK_FILES);
  const hasRun = !!log;
  const hasScoreOutput = !!runDone;
  const sourceLoadedInWorkspace = !!ree._sourceAvailable;
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const IC = svc.IC || Ic.star;
  const level = Math.min(ree._evalLevel ?? 0, LEVELS.length - 1);
  const currentLevel = LEVELS[level];
  const standing = `${level + 1} / ${LEVELS.length}`;
  const completionPct = Math.round((level / (LEVELS.length - 1)) * 100);

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={svc.color}
        icon={IC(18)}
        title={svc.label}
        subtitle={svc.desc}
        tips={descToTwoTierTips(svc.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          {missing.length > 0 && (
            <RequirementsBanner
              status="missing"
              items={missing}
              onAction={onGoFields}
              actionLabel="← Go to Source Repo"
            />
          )}

          {svc.requires && svc.requires.length > 0 && missing.length === 0 && (
            <RequirementsBanner status="met" items={svc.requires} />
          )}

          <ServiceActionSection
            color={svc.color}
            running={running}
            runDone={runDone}
            disabled={running || !sourceLoadedInWorkspace}
            idleLabel="Run"
            runningLabel="Running…"
            helperText={
              sourceLoadedInWorkspace
                ? "Run evaluation with the selected parameters."
                : "Load source into workspace first. Evaluate is enabled only after source download/upload succeeds."
            }
            onRun={() => onRun(svc.key, params)}
          />

          <FieldSection
            title="Evaluate Output · Reproducibility Score"
            icon={IC(14)}
            filledCount={hasScoreOutput ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="repro_level"
              onFocus={() => setFocusedField("repro_level")}
              active={focusedField === "repro_level"}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  marginBottom: 10,
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 12,
                      color: hasScoreOutput ? currentLevel.ink : C.textMuted,
                      marginTop: 2,
                      fontWeight: hasScoreOutput ? 600 : 500,
                    }}
                  >
                    {hasScoreOutput
                      ? `Computed from latest completed Evaluate run · Standing level ${standing}`
                      : "No Evaluate output yet. Complete a run to generate the level."}
                  </div>
                </div>
                <LevelBadge level={level} />
              </div>

              <div
                style={{
                  height: 7,
                  borderRadius: 99,
                  background: C.surfaceAlt,
                  border: `1px solid ${C.border}`,
                  overflow: "hidden",
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    width: `${hasScoreOutput ? completionPct : 0}%`,
                    height: "100%",
                    background: currentLevel.color,
                    transition: "width 0.24s ease",
                  }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {LEVELS.map((levelConfig, idx) => {
                  const reached = hasScoreOutput && idx <= level;
                  const active = hasScoreOutput && idx === level;
                  return (
                    <div
                      key={levelConfig.n}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 8,
                        padding: "7px 8px",
                        borderRadius: 8,
                        border: `1px solid ${active ? `${levelConfig.color}55` : C.border}`,
                        background: active ? levelConfig.bg : "transparent",
                        opacity: hasScoreOutput ? 1 : 0.9,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          fontFamily: F.mono,
                          color: reached ? levelConfig.ink : C.textMuted,
                          background: reached ? levelConfig.bg : C.surfaceAlt,
                          border: `1px solid ${reached ? `${levelConfig.color}55` : C.border}`,
                          borderRadius: 99,
                          padding: "1px 7px",
                          flexShrink: 0,
                          marginTop: 1,
                        }}
                      >
                        L{levelConfig.n}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: 12,
                            fontWeight: active ? 700 : 600,
                            color: reached ? C.text : C.textMid,
                          }}
                        >
                          {levelConfig.label}
                        </div>
                        <div style={S_FIELD_HELP_TEXT_SMALL}>{levelConfig.desc}</div>
                        <div
                          style={{
                            marginTop: 5,
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 6,
                              padding: "4px 6px",
                              borderRadius: 6,
                              background: "#fffbeb",
                              border: "1px solid #fde68a",
                            }}
                          >
                            <span
                              style={{
                                display: "flex",
                                color: "#b45309",
                                flexShrink: 0,
                                marginTop: 1,
                              }}
                            >
                              {Ic.info(11)}
                            </span>
                            <span style={{ fontSize: 11, color: "#92400e", lineHeight: 1.35 }}>
                              {levelConfig.problem ||
                                "No major bottleneck called out at this level."}
                            </span>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 6,
                              padding: "4px 6px",
                              borderRadius: 6,
                              background: "#f0fdf4",
                              border: "1px solid #bbf7d0",
                            }}
                          >
                            <span
                              style={{
                                display: "flex",
                                color: "#15803d",
                                flexShrink: 0,
                                marginTop: 1,
                              }}
                            >
                              {Ic.check(11)}
                            </span>
                            <span style={{ fontSize: 11, color: "#166534", lineHeight: 1.35 }}>
                              {levelConfig.fix || "No additional fix suggested at this level."}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </FieldRow>
          </FieldSection>

          <FieldSection
            title="Detected Dependencies"
            icon={Ic.package()}
            subtitle={!hasRun ? "run to scan" : undefined}
            filledCount={depGroups.length > 0 ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="detected_dependencies"
              onFocus={() => setFocusedField("detected_dependencies")}
              active={focusedField === "detected_dependencies"}
            >
              {hasRun ? (
                <>
                  {depGroups.length > 0 ? (
                    <DependencyPanel depGroups={depGroups} />
                  ) : (
                    <div
                      style={{
                        border: `1.5px dashed ${C.borderMid}`,
                        borderRadius: 10,
                        padding: "16px",
                        textAlign: "center",
                        color: C.textMuted,
                        marginBottom: 12,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "center",
                          marginBottom: 6,
                          opacity: 0.4,
                        }}
                      >
                        {Ic.package(20)}
                      </div>
                      <div style={{ fontSize: 12, fontFamily: F.sans }}>
                        No manifest files found
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: C.textMuted,
                          fontFamily: F.sans,
                          marginTop: 3,
                        }}
                      >
                        Add requirements.txt, pyproject.toml, environment.yml, or package.json.
                      </div>
                    </div>
                  )}

                  {(() => {
                    let containerCount = 0;
                    let nixCount = 0;
                    const scan = (nodes: typeof files) => {
                      for (const node of nodes || []) {
                        if (node.type === "folder") scan(node.children);
                        else {
                          const lo = node.name.toLowerCase();
                          if (
                            lo === "dockerfile" ||
                            lo === "containerfile" ||
                            lo.startsWith("dockerfile.") ||
                            lo.startsWith("containerfile.") ||
                            lo === "docker-compose.yml" ||
                            lo === "docker-compose.yaml"
                          )
                            containerCount += 1;
                          if (lo.endsWith(".nix")) nixCount += 1;
                        }
                      }
                    };
                    scan(files || MOCK_FILES);
                    return (
                      <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <span
                          style={{
                            fontSize: 11,
                            color: "#0e7490",
                            background: "#ecfeff",
                            border: "1px solid #a5f3fc",
                            borderRadius: 99,
                            padding: "3px 10px",
                            fontFamily: F.sans,
                            fontWeight: 600,
                          }}
                        >
                          Container files: {containerCount}
                        </span>
                        <span
                          style={{
                            fontSize: 11,
                            color: "#6d28d9",
                            background: "#f5f3ff",
                            border: "1px solid #ddd6fe",
                            borderRadius: 99,
                            padding: "3px 10px",
                            fontFamily: F.sans,
                            fontWeight: 600,
                          }}
                        >
                          Nix files: {nixCount}
                        </span>
                      </div>
                    );
                  })()}
                </>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {[
                    {
                      label: "requirements.txt",
                      hint: "pip — per-package pins",
                      color: "#3b82f6",
                    },
                    { label: "pyproject.toml", hint: "pip / hatch / poetry", color: "#8b5cf6" },
                    { label: "environment.yml", hint: "conda + bioconda", color: "#22c55e" },
                    { label: "package.json", hint: "npm / yarn dependencies", color: "#dc2626" },
                    { label: "Dockerfile", hint: "container environment", color: "#0891b2" },
                    { label: "*.nix", hint: "declarative system env", color: "#7c3aed" },
                  ].map((item) => (
                    <div
                      key={item.label}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "7px 10px",
                        border: `1.5px dashed ${item.color}30`,
                        borderRadius: 8,
                        background: `${item.color}05`,
                        opacity: 0.7,
                      }}
                    >
                      <span style={{ display: "flex", color: item.color, opacity: 0.6 }}>
                        {Ic.file(12)}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          fontFamily: F.mono,
                          color: item.color,
                          fontWeight: 600,
                          flex: 1,
                        }}
                      >
                        {item.label}
                      </span>
                      <span style={{ fontSize: 10, color: C.textMuted, fontFamily: F.sans }}>
                        {item.hint}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </FieldRow>
          </FieldSection>

          <div
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.3,
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            Output
          </div>
          <LogPanel log={log} running={running} />

          <div style={{ padding: "24px 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={svc.key} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["detected_dependencies", "repro_level"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose either detected dependencies or repro level to see Evaluate-specific tips."
        />
      </div>
    </div>
  );
}
