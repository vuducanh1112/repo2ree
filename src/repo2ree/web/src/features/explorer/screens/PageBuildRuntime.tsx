import { useState } from "react";
import { Ic } from "../../../components/Icon";
import {
  C,
  S_FIELD_HELP_TEXT_SMALL,
  S_FIELD_LABEL_TEXT_SM,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FLEX_COL_GAP_8,
  S_FLEX_ROW_CENTER_GAP_6,
  S_FLEX_ROW_GAP_8,
  S_SECTION_LABEL,
  S_SECTION_LABEL_MB12,
  S_STATUS_BADGE_SM_BASE,
  S_TEXT_ITALIC_11,
  S_TEXT_MUTED_11,
  S_WORKFLOW_BUILD_SECTION_WRAP,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../constants/theme";
import { MOCK_FILES } from "../../../services/dummyWorkspaceService";
import type { ServicePageProps } from "./sharedWorkflowUi";

export function PageBuildRuntime({
  svc,
  ree,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onGoFields,
  badges,
  onGo,
  files,
  onFilesChange,
  onReeChange,
  missing,
  params,
  setParam,
  ui,
}: ServicePageProps) {
  const [expectedOutput, setExpectedOutput] = useState(() =>
    ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "",
  );
  const [showManualOverride, setShowManualOverride] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const buildColor = svc.color;
  const imageColor = "#0891b2";
  const metaRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const includeRuntime = !!ree._runtimeIncluded && !!finalRuntime;
  const finalRuntimeFile = finalRuntime
    ? ui.findFileByPath(files || [], finalRuntime) ||
      ui.findFileByPath(files || [], finalRuntime.split("/").pop() || "")
    : null;
  const finalRuntimeSize = finalRuntimeFile
    ? (() => {
        const m = (finalRuntimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
        if (m) return m[1];
        const b = new TextEncoder().encode(finalRuntimeFile.content || "").length;
        if (b < 1024) return `${b} B`;
        if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
        return `${(b / (1024 * 1024)).toFixed(2)} MB`;
      })()
    : null;

  const {
    WorkflowPageHeader,
    FieldSection,
    FieldRow,
    FilePicker,
    ScriptPanel,
    ServiceActionSection,
    RuntimeOutputNode,
    RuntimeField,
    LogPanel,
    NextStepNudge,
    FieldTipsSidebar,
    hoverBg,
    hoverBorderColor,
    hoverColor,
  } = ui;

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={svc.color}
        icon={Ic.cpu(18)}
        title={svc.label}
        subtitle={svc.desc}
        tips={ui.descToTwoTierTips(svc.desc)}
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
                  files={files || MOCK_FILES}
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
                    background: "#ecfeff",
                    border: "1px solid #a5f3fc",
                    color: "#0e7490",
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
                {ui.SVC_SCRIPT_FIELDS[svc.key]?.map((sf) => (
                  <ScriptPanel
                    key={sf.fieldKey}
                    scriptKind={sf.scriptKind || null}
                    fieldKey={sf.fieldKey}
                    files={files || MOCK_FILES}
                    onFilesChange={onFilesChange}
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
                    fontFamily: "JetBrains Mono, monospace",
                    color: C.text,
                    background: C.surface,
                    width: "100%",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              {svc.params && svc.params.length > 0 && (
                <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                  <div style={S_SECTION_LABEL_MB12}>Additional Parameters</div>
                  <div
                    style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end" }}
                  >
                    {svc.params.map((p) => (
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
                            onClick={() => setParam(p.key, !params[p.key])}
                            style={{
                              width: 34,
                              height: 19,
                              borderRadius: 99,
                              border: "none",
                              cursor: "pointer",
                              background: params[p.key] ? buildColor : C.borderMid,
                              transition: "background 0.2s",
                              position: "relative",
                            }}
                          >
                            <div
                              style={{
                                position: "absolute",
                                top: 2,
                                left: params[p.key] ? 17 : 2,
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
                            value={String(params[p.key] ?? "")}
                            onChange={(event) => setParam(p.key, event.target.value)}
                            style={{
                              border: `1.5px solid ${C.border}`,
                              borderRadius: 6,
                              padding: "5px 8px",
                              fontSize: 11,
                              fontFamily: "JetBrains Mono, monospace",
                              color: C.text,
                              background: C.surface,
                            }}
                          >
                            {p.options.map((o) => (
                              <option key={o} value={o}>
                                {o}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            value={String(params[p.key] ?? "")}
                            onChange={(event) => setParam(p.key, event.target.value)}
                            style={{
                              border: `1.5px solid ${C.border}`,
                              borderRadius: 6,
                              padding: "5px 8px",
                              fontSize: 11,
                              fontFamily: "JetBrains Mono, monospace",
                              color: C.text,
                              background: C.surface,
                              boxSizing: "border-box",
                            }}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </FieldRow>
          </FieldSection>

          <ServiceActionSection
            color={buildColor}
            running={running}
            runDone={runDone}
            disabled={running || missing.length > 0}
            idleLabel="Run build"
            runningLabel="Building…"
            doneLabel="Re-build"
            helperText="Execute the build script and record build logs."
            onRun={() => onRun(svc.key, { ...params, _expectedOutput: expectedOutput })}
          />

          <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
            <div style={S_SECTION_LABEL_MB12}>Step 3: Verify Build Output</div>
            <RuntimeOutputNode
              expectedOutput={expectedOutput}
              buildDone={runDone}
              ree={ree}
              imageColor={imageColor}
              files={files || MOCK_FILES}
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
                    border: "1.5px solid #fdba74",
                    background: "#fff7ed",
                    cursor: "pointer",
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#9a3412",
                    boxShadow: "0 1px 2px rgba(154,52,18,0.14)",
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
                      background: "#fed7aa",
                      color: "#9a3412",
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
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    background: metaRuntime ? "#f0fdf4" : C.surfaceAlt,
                    border: `1.5px solid ${metaRuntime ? "#bbf7d0" : C.border}`,
                    borderRadius: 8,
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
                      background: metaRuntime ? "#dcfce7" : `${C.border}40`,
                    }}
                  >
                    <span style={{ color: metaRuntime ? "#16a34a" : C.textMuted, display: "flex" }}>
                      {Ic.files(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: 0.8,
                        color: metaRuntime ? "#16a34a" : C.textMuted,
                        opacity: 0.7,
                        marginBottom: 1,
                        fontWeight: 700,
                      }}
                    >
                      ree.runtime
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: "JetBrains Mono, monospace",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: metaRuntime ? "#15803d" : C.textMuted,
                      }}
                    >
                      {metaRuntime || <span style={S_TEXT_ITALIC_11}>not set</span>}
                    </div>
                  </div>
                  {metaRuntime && (
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
                <RuntimeField
                  locked={false}
                  ree={ree}
                  onChange={onReeChange}
                  onFocus={() => setFocusedField("runtime")}
                  active={false}
                  files={files || MOCK_FILES}
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
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    background: finalRuntime ? "#f0fdf4" : C.surfaceAlt,
                    border: `1.5px solid ${finalRuntime ? "#bbf7d0" : C.border}`,
                    borderRadius: 8,
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
                      background: finalRuntime ? "#dcfce7" : `${C.border}40`,
                    }}
                  >
                    <span
                      style={{ color: finalRuntime ? "#16a34a" : C.textMuted, display: "flex" }}
                    >
                      {Ic.archive(14)}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: 0.8,
                        color: finalRuntime ? "#16a34a" : C.textMuted,
                        opacity: 0.7,
                        marginBottom: 1,
                        fontWeight: 700,
                      }}
                    >
                      ree.runtime
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: "JetBrains Mono, monospace",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: finalRuntime ? "#15803d" : C.textMuted,
                      }}
                    >
                      {finalRuntime || (
                        <span style={S_TEXT_ITALIC_11}>
                          not set yet — run build or set manually
                        </span>
                      )}
                    </div>
                  </div>
                  {finalRuntimeSize && (
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: "JetBrains Mono, monospace",
                        fontWeight: 700,
                        color: finalRuntime ? "#166534" : C.textMuted,
                        background: finalRuntime ? "#dcfce7" : C.surfaceAlt,
                        border: `1px solid ${finalRuntime ? "#86efac" : C.border}`,
                        borderRadius: 4,
                        padding: "2px 7px",
                        flexShrink: 0,
                      }}
                    >
                      {finalRuntimeSize}
                    </span>
                  )}
                  {finalRuntime && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginLeft: 4,
                        paddingLeft: 8,
                        borderLeft: `1px solid ${finalRuntime ? "#bbf7d0" : C.border}`,
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                        <div
                          style={{
                            fontSize: 10,
                            textTransform: "uppercase",
                            letterSpacing: 0.7,
                            color: includeRuntime ? "#164e63" : C.textMuted,
                            fontWeight: 700,
                          }}
                        >
                          Included
                        </div>
                        <div
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: includeRuntime ? "#0891b2" : C.textMuted,
                          }}
                        >
                          {includeRuntime ? "Yes" : "No"}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onReeChange?.({ ...ree, _runtimeIncluded: !includeRuntime })}
                        style={{
                          width: 34,
                          height: 20,
                          border: "none",
                          borderRadius: 99,
                          cursor: "pointer",
                          background: includeRuntime ? "#06b6d4" : C.borderMid,
                          position: "relative",
                        }}
                      >
                        <span
                          style={{
                            position: "absolute",
                            top: 2,
                            left: includeRuntime ? 16 : 2,
                            width: 16,
                            height: 16,
                            borderRadius: "50%",
                            background: "#fff",
                            transition: "left 0.2s",
                          }}
                        />
                      </button>
                    </div>
                  )}
                  {finalRuntime && (
                    <span
                      style={{
                        ...S_STATUS_BADGE_SM_BASE,
                        color: "#16a34a",
                        background: "#f0fdf4",
                        border: "1px solid #bbf7d0",
                      }}
                    >
                      FINAL
                    </span>
                  )}
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
            <div style={{ ...S_SECTION_LABEL, marginBottom: 8 }}>Output</div>
            <LogPanel log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge stepKey={svc.key} badges={badges || {}} onGo={onGo || (() => {})} />
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
