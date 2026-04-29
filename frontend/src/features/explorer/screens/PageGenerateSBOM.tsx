import type React from "react";
import { useMemo, useState } from "react";
import { Ic } from "../../../components/Icon";
import { PAGE } from "../../../constants/pages";
import {
  C,
  F,
  S_ACTION_BUTTON_BASE,
  S_FIELD_STACK_GAP_14,
  S_SECTION_LABEL,
  S_TEXT_ITALIC_11,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_SCRIPTS_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../constants/theme";
import { MOCK_FILES } from "../../../services/dummyWorkspaceService";
import type { AutomationStepRunParams } from "../../../types";
import { ScriptPanel } from "../components/inputs/scriptAndFile";
import {
  descToTwoTierTips,
  FieldRow,
  FieldSection,
  FieldTipsSidebar,
} from "../components/workflow/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../components/workflow/pageChrome";
import { ServiceActionSection, WorkflowLogSection } from "../components/workflow/servicePanels";
import {
  RUNTIME_STATUS_BADGE_STYLE,
  workflowStatusBadgeStyle,
  workflowStatusCardStyle,
  workflowStatusIconWrapStyle,
  workflowStatusKeyStyle,
  workflowStatusValueStyle,
} from "../components/workflow/statusUiStyles";
import { SVC_SCRIPT_FIELDS } from "./sharedWorkflowConstants";
import { findFileByPath } from "./sharedWorkflowHelpers";
import type { ServicePageProps } from "./sharedWorkflowUi";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

const SBOM_PARSE_CHAR_LIMIT = 300_000;
const SBOM_PREVIEW_CHAR_LIMIT = 120_000;

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
  onCancel,
  onGo,
  onGoFields,
  missing,
  params,
  onReeChange,
  onFilesChange,
  onPersistWorkspaceFile,
}: ServicePageProps) {
  const sbomParams: AutomationStepRunParams<"sbom"> = {
    ...(params as AutomationStepRunParams<"sbom">),
    produced_runtime_path: ree.runtime,
  };

  const files = virtualFiles;

  const sbomColor = svc.color;
  const rt = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
  const isTb = rt && /\.(tar\.gz|tgz)$/i.test(rt);
  const hasSbom = !!(ree.sbom && ree.sbom !== "__skipped__");
  const sbomNode = hasSbom ? findFileByPath(files || [], ree.sbom) : null;
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const sbomText = sbomNode?.content || "";
  const sbomUnavailable = !!sbomNode && !sbomNode.content && (sbomNode.size || 0) > 0;
  const sbomTooLargeForPreview = sbomText.length > SBOM_PREVIEW_CHAR_LIMIT;
  const sbomPreviewText = sbomTooLargeForPreview
    ? `${sbomText.slice(0, SBOM_PREVIEW_CHAR_LIMIT)}\n\n... preview truncated ...`
    : sbomText;

  const sbomScripts = SVC_SCRIPT_FIELDS[svc.key] || [];
  const pkgCount = useMemo(() => {
    if (!hasSbom || !sbomNode?.content) return null;
    if (sbomNode.content.length > SBOM_PARSE_CHAR_LIMIT) return null;
    try {
      return JSON.parse(sbomNode.content)?.packages?.length ?? null;
    } catch {
      return null;
    }
  }, [hasSbom, sbomNode?.content]);

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
                <div style={workflowStatusCardStyle(!!rt, sbomColor)}>
                  <div style={workflowStatusIconWrapStyle(!!rt, sbomColor)}>
                    <span style={{ color: rt ? sbomColor : C.textMuted, display: "flex" }}>
                      {isTb ? Ic.archive(14) : Ic.cpu(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={workflowStatusKeyStyle(!!rt, sbomColor)}>
                      Scan target · ree.runtime
                    </div>
                    <div style={workflowStatusValueStyle(!!rt, sbomColor)}>
                      {rt || (
                        <span style={S_TEXT_ITALIC_11}>
                          not set — set a runtime in the Build Runtime step first
                        </span>
                      )}
                    </div>
                  </div>
                  {rt && (
                    <span style={workflowStatusBadgeStyle(sbomColor)}>
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
            onCancel={() => onCancel?.(svc.key)}
            onRun={() => onRun(svc.key, sbomParams)}
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
              <div style={{ ...workflowStatusCardStyle(hasSbom, "#16a34a"), marginBottom: 12 }}>
                <div style={workflowStatusIconWrapStyle(hasSbom, "#16a34a")}>
                  <span style={{ color: hasSbom ? "#16a34a" : C.textMuted, display: "flex" }}>
                    {Ic.package(14)}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={workflowStatusKeyStyle(hasSbom, "#16a34a")}>ree.sbom</div>
                  <div style={workflowStatusValueStyle(hasSbom, "#15803d")}>
                    {hasSbom ? (
                      ree.sbom
                    ) : (
                      <span style={S_TEXT_ITALIC_11}>not set — click Generate SBOM</span>
                    )}
                  </div>
                </div>
                {hasSbom && <span style={RUNTIME_STATUS_BADGE_STYLE}>SET</span>}
              </div>

              {hasSbom ? (
                (() => {
                  if (!sbomNode)
                    return (
                      <div style={{ color: C.textMuted }}>
                        SBOM file was set but is not present in files.
                      </div>
                    );
                  if (sbomUnavailable)
                    return (
                      <div style={{ color: C.textMuted }}>
                        SBOM file is present but too large to inline in memory. Use the Files page
                        to inspect/download it.
                      </div>
                    );
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
                            {sbomPreviewText}
                          </pre>
                        </div>
                      </div>
                      {sbomTooLargeForPreview && (
                        <div style={{ marginTop: 8, fontSize: 11, color: C.textMuted }}>
                          Preview truncated to keep the UI responsive.
                        </div>
                      )}
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
                  onPersistWorkspaceFile={onPersistWorkspaceFile}
                  ree={ree}
                  onReeChange={onReeChange}
                />
              ))}
            </div>
          )}

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <WorkflowLogSection log={log} running={running} />
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
