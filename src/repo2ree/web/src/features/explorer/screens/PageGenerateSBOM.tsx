import type React from "react";
import { useState } from "react";
import { Ic } from "../../../components/Icon";
import { PAGE } from "../../../constants/pages";
import {
  C,
  F,
  S_ACTION_BUTTON_BASE,
  S_FIELD_STACK_GAP_14,
  S_SECTION_LABEL,
  S_SECTION_LABEL_SMALL,
  S_STATUS_BADGE_SM_BASE,
  S_TEXT_ITALIC_11,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_SCRIPTS_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../constants/theme";
import { MOCK_FILES } from "../../../services/dummyWorkspaceService";
import { LogPanel } from "../components/inputs/logPanel";
import { ScriptPanel } from "../components/inputs/scriptAndFile";
import {
  descToTwoTierTips,
  FieldRow,
  FieldSection,
  FieldTipsSidebar,
} from "../components/workflow/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../components/workflow/pageChrome";
import { ServiceActionSection } from "../components/workflow/servicePanels";
import { SVC_SCRIPT_FIELDS } from "./sharedWorkflowConstants";
import { findFileByPath } from "./sharedWorkflowHelpers";
import type { ServicePageProps } from "./sharedWorkflowUi";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function PageGenerateSBOM({
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
  onReeChange,
  onFilesChange,
}: ServicePageProps) {
  const files = virtualFiles;

  const sbomColor = svc.color;
  const rt = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
  const isTb = rt && /\.(tar\.gz|tgz)$/i.test(rt);
  const hasSbom = !!(ree.sbom && ree.sbom !== "__skipped__");
  const sbomNode = hasSbom ? findFileByPath(files || [], ree.sbom) : null;
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const sbomScripts = SVC_SCRIPT_FIELDS[svc.key] || [];

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={svc.color}
        icon={Ic.package(18)}
        title="Generate SBOM"
        subtitle="Generate a machine-readable SBOM from the runtime image/tarball"
        tips={descToTwoTierTips(svc.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          <FieldSection
            title="Step 1: Runtime Input"
            icon={Ic.cpu()}
            filledCount={rt ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="runtime"
              onFocus={() => setFocusedField("runtime")}
              active={focusedField === "runtime"}
            >
              <div style={S_FIELD_STACK_GAP_14}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    background: rt ? "#ecfeff" : C.surfaceAlt,
                    border: `1.5px solid ${rt ? `${sbomColor}50` : C.border}`,
                    borderRadius: 9,
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 7,
                      flexShrink: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: `${rt ? sbomColor : C.textMuted}18`,
                    }}
                  >
                    <span style={{ color: rt ? sbomColor : C.textMuted, display: "flex" }}>
                      {isTb ? Ic.archive(14) : Ic.cpu(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        ...S_SECTION_LABEL_SMALL,
                        letterSpacing: 0.8,
                        color: rt ? sbomColor : C.textMuted,
                        opacity: 0.7,
                        marginBottom: 1,
                      }}
                    >
                      Scan target · ree.runtime
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: F.mono,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: rt ? sbomColor : C.textMuted,
                      }}
                    >
                      {rt || (
                        <span style={S_TEXT_ITALIC_11}>
                          not set — set a runtime in the Build Runtime step first
                        </span>
                      )}
                    </div>
                  </div>
                  {rt && (
                    <span
                      style={{
                        ...S_STATUS_BADGE_SM_BASE,
                        color: sbomColor,
                        background: `${sbomColor}12`,
                        border: `1px solid ${sbomColor}40`,
                      }}
                    >
                      {isTb ? "TARBALL" : "IMAGE"}
                    </span>
                  )}
                </div>

                {!rt && (
                  <button
                    type="button"
                    onClick={() => onGo(PAGE.BUILD)}
                    style={{
                      ...actionBtn({
                        border: `1px solid ${sbomColor}40`,
                        borderRadius: 6,
                        padding: "5px 10px",
                        fontSize: 12,
                        color: sbomColor,
                        background: `${sbomColor}12`,
                      }),
                      width: "fit-content",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      cursor: "pointer",
                    }}
                  >
                    {Ic.chevR(12)} Go to Build Runtime
                  </button>
                )}
              </div>
            </FieldRow>
          </FieldSection>

          <ServiceActionSection
            color={sbomColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Generate SBOM"
            runningLabel="Generating…"
            doneLabel="Regenerate SBOM"
            helperText="Generate an SPDX JSON SBOM from the selected runtime."
            onRun={() => onRun(svc.key, params)}
          />

          <FieldSection
            title="Step 2: Produced SBOM"
            icon={Ic.package()}
            filledCount={hasSbom ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="sbom"
              onFocus={() => setFocusedField("sbom")}
              active={focusedField === "sbom"}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 14px",
                  background: hasSbom ? "#f0fdf4" : C.surfaceAlt,
                  border: `1.5px solid ${hasSbom ? "#bbf7d0" : C.border}`,
                  borderRadius: 9,
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 7,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: hasSbom ? "#dcfce7" : `${C.border}40`,
                  }}
                >
                  <span style={{ color: hasSbom ? "#16a34a" : C.textMuted, display: "flex" }}>
                    {Ic.package(14)}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      ...S_SECTION_LABEL_SMALL,
                      letterSpacing: 0.8,
                      color: hasSbom ? "#16a34a" : C.textMuted,
                      opacity: 0.7,
                      marginBottom: 1,
                    }}
                  >
                    ree.sbom
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      fontFamily: F.mono,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: hasSbom ? "#15803d" : C.textMuted,
                    }}
                  >
                    {hasSbom ? (
                      ree.sbom
                    ) : (
                      <span style={S_TEXT_ITALIC_11}>not set — click Generate SBOM</span>
                    )}
                  </div>
                </div>
                {hasSbom && (
                  <span
                    style={{
                      ...S_STATUS_BADGE_SM_BASE,
                      color: "#16a34a",
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                    }}
                  >
                    SET
                  </span>
                )}
              </div>

              {hasSbom ? (
                (() => {
                  if (!sbomNode)
                    return (
                      <div style={{ color: C.textMuted }}>
                        SBOM file was set but is not present in files.
                      </div>
                    );
                  let pkgCount = null;
                  try {
                    pkgCount = JSON.parse(sbomNode.content ?? "{}")?.packages?.length ?? null;
                  } catch {}
                  return (
                    <div>
                      <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>SBOM Preview</div>
                      <div
                        style={{
                          border: `1px solid ${sbomColor}20`,
                          borderRadius: 10,
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "10px 14px",
                            background: `${sbomColor}08`,
                            borderBottom: `1px solid ${sbomColor}20`,
                          }}
                        >
                          <span style={{ color: sbomColor, display: "flex" }}>{Ic.file(13)}</span>
                          <span
                            style={{
                              fontSize: 13,
                              fontFamily: F.mono,
                              fontWeight: 700,
                              color: sbomColor,
                              flex: 1,
                            }}
                          >
                            {ree.sbom}
                          </span>
                          {pkgCount !== null && (
                            <span
                              style={{
                                fontSize: 11,
                                fontFamily: F.sans,
                                color: sbomColor,
                                background: `${sbomColor}15`,
                                border: `1px solid ${sbomColor}30`,
                                borderRadius: 10,
                                padding: "1px 8px",
                              }}
                            >
                              {pkgCount} package{pkgCount !== 1 ? "s" : ""}
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            background: "#0d1117",
                            padding: "14px 16px",
                            maxHeight: 340,
                            overflowY: "auto",
                          }}
                        >
                          <pre
                            style={{
                              margin: 0,
                              fontSize: 11,
                              fontFamily: F.mono,
                              color: "#7ee787",
                              lineHeight: 1.6,
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-all",
                            }}
                          >
                            {sbomNode.content}
                          </pre>
                        </div>
                      </div>
                    </div>
                  );
                })()
              ) : (
                <div style={{ color: C.textMuted }}>No SBOM generated yet.</div>
              )}
            </FieldRow>
          </FieldSection>

          {sbomScripts.length > 0 && (
            <div style={S_WORKFLOW_PAGE_SCRIPTS_WRAP}>
              <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Scripts</div>
              {sbomScripts.map((sf) => (
                <ScriptPanel
                  key={sf.fieldKey}
                  scriptKind={sf.scriptKind || null}
                  fieldKey={sf.fieldKey}
                  files={files || MOCK_FILES}
                  onFilesChange={onFilesChange}
                  ree={ree}
                  onReeChange={onReeChange}
                />
              ))}
            </div>
          )}

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>Output</div>
            <LogPanel log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge stepKey={PAGE.SBOM} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["runtime", "sbom"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
        />
      </div>
    </div>
  );
}
