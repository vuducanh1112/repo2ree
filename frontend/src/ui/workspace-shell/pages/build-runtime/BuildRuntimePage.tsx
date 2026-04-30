import { useMemo, useState } from "react";
import type { AutomationStepRunParams } from "../../../../application/workflow/WorkflowTypes";
import { Ic } from "../../../shared/components/Icon";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverColor,
  S_FIELD_HELP_TEXT_SMALL,
  S_FIELD_LABEL_TEXT_SM,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FLEX_COL_GAP_8,
  S_FLEX_ROW_CENTER_GAP_6,
  S_FLEX_ROW_GAP_8,
  S_SECTION_LABEL,
  S_SECTION_LABEL_MB12,
  S_TEXT_ITALIC_11,
  S_TEXT_MUTED_11,
  S_WORKFLOW_BUILD_SECTION_WRAP,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import {
  descToTwoTierTips,
  FieldRow,
  FieldSection,
  FieldTipsSidebar,
} from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { FilePicker, ScriptPanel } from "../../components/scriptAndFile";
import { RuntimeField } from "../../components/sourceRuntime";
import {
  RUNTIME_STATUS_BADGE_STYLE,
  runtimeFieldCardStyle,
  runtimeFieldIconColor,
  runtimeFieldIconWrapStyle,
  runtimeFieldKeyStyle,
  runtimeFieldValueStyle,
  runtimeIncludedLabelStyle,
  runtimeIncludedToggleKnobStyle,
  runtimeIncludedToggleTrackStyle,
  runtimeIncludedValueStyle,
  runtimeIncludedWrapStyle,
  runtimeSizeBadgeStyle,
  workflowToneSurfaceStyle,
} from "../../components/statusUiStyles";
import {
  RuntimeOutputNode,
  WorkflowLogSection,
  WorkflowRunActionSection,
} from "../../components/workflowRunPanels";
import { SVC_SCRIPT_FIELDS } from "../sharedWorkflowConstants";
import { findFileByPath } from "../sharedWorkflowHelpers";
import type { WorkflowPageProps } from "../sharedWorkflowUi";

function formatByteSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function deriveRuntimeFileSize(
  runtimeFile: { size?: number; content?: string } | null,
): string | null {
  if (!runtimeFile) return null;
  if (typeof runtimeFile.size === "number" && runtimeFile.size > 0) {
    return formatByteSize(runtimeFile.size);
  }
  const sizeMatch = (runtimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
  if (sizeMatch) {
    return sizeMatch[1];
  }
  const bytes = new TextEncoder().encode(runtimeFile.content || "").length;
  return formatByteSize(bytes);
}

export function PageBuildRuntime({
  workflow,
  ree,
  badges,
  workspaceFiles,
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
  setParam,
  onReeChange,
  onFilesChange,
  onPersistWorkspaceFile,
}: WorkflowPageProps) {
  const files = workspaceFiles;

  const [expectedOutput, setExpectedOutput] = useState(() =>
    ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "",
  );
  const buildParams: AutomationStepRunParams<"build"> = {
    ...(params as AutomationStepRunParams<"build">),
    build_runtime_script_path: ree.build_runtime_script,
    produced_runtime_path: expectedOutput,
    _expectedOutput: expectedOutput,
  };
  const [showManualOverride, setShowManualOverride] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const buildColor = workflow.color;
  const imageColor = "#0891b2";
  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const metaRuntime = finalRuntime || null;
  const includeRuntime = !!ree._runtimeIncluded && !!finalRuntime;
  const finalRuntimeFile = useMemo(() => {
    if (!finalRuntime) return null;
    return (
      findFileByPath(files || [], finalRuntime) ||
      findFileByPath(files || [], finalRuntime.split("/").pop() || "")
    );
  }, [files, finalRuntime]);
  const finalRuntimeSize = useMemo(
    () => deriveRuntimeFileSize(finalRuntimeFile),
    [finalRuntimeFile],
  );

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={workflow.color}
        icon={Ic.cpu(18)}
        title={workflow.label}
        subtitle={workflow.desc}
        tips={descToTwoTierTips(workflow.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        timestampPrefix="Last built"
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          <FieldSection
            title="Step 1: Build Script"
            icon={Ic.cpu()}
            filledCount={ree.build_runtime_script ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="build_runtime_script"
              onFocus={() => setFocusedField("build_runtime_script")}
              active={focusedField === "build_runtime_script"}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <div style={S_FLEX_ROW_CENTER_GAP_6}>
                  <span style={S_FIELD_LABEL_TEXT_SM}>Shell script</span>
                  <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
                </div>
                <div style={S_FIELD_HELP_TEXT_SMALL}>
                  Script that builds your runtime environment. The script is responsible for
                  exporting the runtime to the file specified in "Expected output" below.
                </div>
                <FilePicker
                  disabled={false}
                  value={ree.build_runtime_script}
                  onChange={(v) => onReeChange?.({ ...ree, build_runtime_script: v })}
                  files={files || []}
                  placeholder="build_runtime.sh"
                  filterFn={(p) => /\.sh$/i.test(p)}
                />
              </div>

              {!ree.build_runtime_script && (
                <div
                  style={{
                    marginTop: 12,
                    padding: "9px 12px",
                    borderRadius: 7,
                    ...workflowToneSurfaceStyle("info"),
                    fontSize: 11,
                    lineHeight: 1.4,
                  }}
                >
                  No build script yet? Use a predefined default script in the editor below (Docker,
                  Nix, Conda, Python venv).
                </div>
              )}

              <div style={{ marginTop: 14 }}>
                <div style={{ ...S_SECTION_LABEL, marginBottom: 10 }}>Build Script Editor</div>
                {SVC_SCRIPT_FIELDS[workflow.key]?.map((sf) => (
                  <ScriptPanel
                    key={sf.fieldKey}
                    scriptKind={sf.scriptKind || null}
                    fieldKey={sf.fieldKey}
                    files={files || []}
                    onFilesChange={onFilesChange}
                    onPersistWorkspaceFile={onPersistWorkspaceFile}
                    ree={ree}
                    onReeChange={onReeChange}
                    onTemplateSuggestedOutput={(out) => setExpectedOutput(out)}
                    saveToWorkspaceOnly
                  />
                ))}
              </div>
            </FieldRow>
          </FieldSection>

          <FieldSection
            title="Step 2: Expected Output"
            icon={Ic.archive()}
            filledCount={expectedOutput ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="runtime"
              onFocus={() => setFocusedField("runtime")}
              active={focusedField === "runtime"}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <div style={S_FLEX_ROW_CENTER_GAP_6}>
                  <span style={S_FIELD_LABEL_TEXT_SM}>Exported runtime file path</span>
                  <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>
                </div>
                <div style={S_FIELD_HELP_TEXT_SMALL}>
                  The filepath where your build script will export the runtime (e.g.,{" "}
                  <code style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10 }}>
                    runtime.tar.gz
                  </code>
                  ).
                </div>
                <input
                  value={expectedOutput}
                  onChange={(event) => setExpectedOutput(event.target.value)}
                  onFocus={() => setFocusedField("runtime")}
                  placeholder="runtime.tar.gz"
                  style={{
                    border: `1.5px solid ${expectedOutput ? C.accentBorder : C.border}`,
                    borderRadius: 6,
                    padding: "5px 8px",
                    fontSize: 11,
                    fontFamily: F.mono,
                    color: C.text,
                    background: C.surface,
                    width: "100%",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              {workflow.params && workflow.params.length > 0 && (
                <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                  <div style={S_SECTION_LABEL_MB12}>Additional Parameters</div>
                  <div
                    style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}
                  >
                    {workflow.params.map((p) => {
                      const paramValue = params[p.key as keyof typeof params];

                      return (
                        <div
                          key={p.key}
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 5,
                            flex: "0 1 auto",
                          }}
                        >
                          <div
                            style={{
                              fontSize: 12,
                              fontWeight: 600,
                              color: C.textMid,
                            }}
                          >
                            {p.label}
                          </div>
                          {p.hint && <div style={S_FIELD_HELP_TEXT_SMALL}>{p.hint}</div>}
                          {p.type === "bool" ? (
                            <button
                              type="button"
                              onClick={() => setParam(p.key, !paramValue)}
                              style={{
                                width: 34,
                                height: 19,
                                borderRadius: 99,
                                border: "none",
                                cursor: "pointer",
                                background: paramValue ? buildColor : C.borderMid,
                                transition: "background 0.2s",
                                position: "relative",
                              }}
                            >
                              <div
                                style={{
                                  position: "absolute",
                                  top: 2,
                                  left: paramValue ? 17 : 2,
                                  width: 15,
                                  height: 15,
                                  borderRadius: "50%",
                                  background: "#fff",
                                  transition: "left 0.2s",
                                  boxShadow: "0 1px 3px rgba(0,0,0,0.18)",
                                }}
                              />
                            </button>
                          ) : p.type === "select" ? (
                            <select
                              value={String(paramValue ?? "")}
                              onChange={(event) => setParam(p.key, event.target.value)}
                              style={{
                                border: `1.5px solid ${C.border}`,
                                borderRadius: 6,
                                padding: "5px 8px",
                                fontSize: 11,
                                fontFamily: F.mono,
                                color: C.text,
                                background: C.surface,
                              }}
                            >
                              {(p.options ?? []).map((o) => (
                                <option key={o} value={o}>
                                  {o}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              value={String(paramValue ?? "")}
                              onChange={(event) => setParam(p.key, event.target.value)}
                              style={{
                                border: `1.5px solid ${C.border}`,
                                borderRadius: 6,
                                padding: "5px 8px",
                                fontSize: 11,
                                fontFamily: F.mono,
                                color: C.text,
                                background: C.surface,
                                boxSizing: "border-box",
                              }}
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </FieldRow>
          </FieldSection>

          <WorkflowRunActionSection
            color={buildColor}
            running={running}
            runDone={runDone}
            disabled={running || missing.length > 0}
            idleLabel="Run build"
            runningLabel="Building…"
            doneLabel="Re-build"
            helperText="Execute the build script and record build logs."
            onCancel={() => onCancel?.(workflow.key)}
            onRun={() => onRun(workflow.key, buildParams)}
          />

          <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
            <div style={S_SECTION_LABEL_MB12}>Step 3: Verify Build Output</div>
            <RuntimeOutputNode
              expectedOutput={expectedOutput}
              buildDone={runDone}
              ree={ree}
              imageColor={imageColor}
              files={files || []}
            />
          </div>

          {!showManualOverride ? (
            <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => setShowManualOverride(true)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "9px 14px",
                    borderRadius: 9,
                    ...workflowToneSurfaceStyle("warn"),
                    borderWidth: "1.5px",
                    borderStyle: "solid",
                    cursor: "pointer",
                    fontSize: 13,
                    fontWeight: 700,
                    boxShadow: "0 1px 2px rgba(146,64,14,0.14)",
                    transition: "all 0.14s ease",
                  }}
                  {...hoverBg("#ffedd5", "#fff7ed")}
                  {...hoverBorderColor("#fb923c", "#fdba74")}
                >
                  <span
                    style={{
                      display: "flex",
                      width: 18,
                      height: 18,
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 5,
                      background: "#fde68a",
                      color: "#92400e",
                    }}
                  >
                    {Ic.x(12)}
                  </span>
                  Skip building the runtime and manually set it instead. Not Recommended, please try
                  to make it work using a build script and running the build.
                </button>
                <div style={S_TEXT_MUTED_11}>
                  Only do this if for some reason you cannot build the runtime automatically.
                </div>
              </div>
            </div>
          ) : (
            <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
              <div style={S_SECTION_LABEL_MB12}>Manual Override</div>
              <div style={S_FLEX_COL_GAP_8}>
                <div style={S_FIELD_HELP_TEXT_SMALL}>
                  You chose to skip building — set the runtime field manually. This will override
                  any automatic detection.
                </div>
                <div style={runtimeFieldCardStyle(!!metaRuntime)}>
                  <div style={runtimeFieldIconWrapStyle(!!metaRuntime)}>
                    <span style={{ color: runtimeFieldIconColor(!!metaRuntime), display: "flex" }}>
                      {Ic.files(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={runtimeFieldKeyStyle(!!metaRuntime)}>ree.runtime</div>
                    <div style={runtimeFieldValueStyle(!!metaRuntime)}>
                      {metaRuntime || <span style={S_TEXT_ITALIC_11}>not set</span>}
                    </div>
                  </div>
                  {metaRuntime && <span style={RUNTIME_STATUS_BADGE_STYLE}>SET</span>}
                </div>
                <RuntimeField
                  locked={false}
                  ree={ree}
                  onChange={onReeChange}
                  onFocus={() => setFocusedField("runtime")}
                  active={false}
                  files={files || []}
                />
                <div style={S_FLEX_ROW_GAP_8}>
                  <button
                    type="button"
                    onClick={() => setShowManualOverride(false)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 7,
                      padding: "7px 11px",
                      borderRadius: 7,
                      border: `1.5px solid ${C.borderMid}`,
                      background: C.surfaceAlt,
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 700,
                      color: C.textMid,
                      transition: "all 0.14s ease",
                    }}
                    {...hoverBg(C.surface, C.surfaceAlt)}
                    {...hoverBorderColor(C.accentBorder, C.borderMid)}
                    {...hoverColor(C.accent, C.textMid)}
                  >
                    {Ic.arrowLeft(12)} Back to build flow
                  </button>
                </div>
              </div>
            </div>
          )}

          <FieldSection
            title="Step 4: Final Runtime Field"
            icon={Ic.archive()}
            filledCount={finalRuntime ? 1 : 0}
            totalCount={1}
          >
            <FieldRow
              fieldKey="runtime"
              onFocus={() => setFocusedField("runtime")}
              active={focusedField === "runtime"}
            >
              <div style={S_FLEX_COL_GAP_8}>
                <div style={runtimeFieldCardStyle(!!finalRuntime)}>
                  <div style={runtimeFieldIconWrapStyle(!!finalRuntime)}>
                    <span style={{ color: runtimeFieldIconColor(!!finalRuntime), display: "flex" }}>
                      {Ic.archive(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={runtimeFieldKeyStyle(!!finalRuntime)}>ree.runtime</div>
                    <div style={runtimeFieldValueStyle(!!finalRuntime)}>
                      {finalRuntime || (
                        <span style={S_TEXT_ITALIC_11}>
                          not set yet — run build or set manually
                        </span>
                      )}
                    </div>
                  </div>
                  {finalRuntimeSize && (
                    <span style={runtimeSizeBadgeStyle(!!finalRuntime)}>{finalRuntimeSize}</span>
                  )}
                  {finalRuntime && (
                    <div style={runtimeIncludedWrapStyle(!!finalRuntime)}>
                      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                        <div style={runtimeIncludedLabelStyle(includeRuntime)}>Included</div>
                        <div style={runtimeIncludedValueStyle(includeRuntime)}>
                          {includeRuntime ? "Yes" : "No"}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onReeChange?.({ ...ree, _runtimeIncluded: !includeRuntime })}
                        style={runtimeIncludedToggleTrackStyle(includeRuntime)}
                      >
                        <span style={runtimeIncludedToggleKnobStyle(includeRuntime)} />
                      </button>
                    </div>
                  )}
                  {finalRuntime && <span style={RUNTIME_STATUS_BADGE_STYLE}>FINAL</span>}
                </div>
                <div style={S_FIELD_HELP_TEXT_SMALL}>
                  {finalRuntime
                    ? includeRuntime
                      ? "Runtime will be bundled in the REE archive."
                      : "Runtime will not be bundled in the REE archive."
                    : "Set a runtime value first."}
                </div>
              </div>
            </FieldRow>
          </FieldSection>

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <WorkflowLogSection log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge stepKey={workflow.key} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["build_runtime_script", "runtime"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
        />
      </div>
    </div>
  );
}
