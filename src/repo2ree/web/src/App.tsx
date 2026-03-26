import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Ic, Svg } from "./components/Icon";
import { Toast } from "./components/Toast";
import { FIELD_META } from "./constants/fieldMeta";
import { LEVELS } from "./constants/levels";
import { APP_PAGE, FIELD_TO_PAGE, PAGE } from "./constants/pages";
import { defaultParamsForService, initialServiceParams, SERVICES } from "./constants/services";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverBrightness,
  hoverColor,
  hoverIf,
  S_ACTION_BUTTON_BASE,
  S_FIELD_ROW_BASE,
  S_FIELD_ROW_CONTENT,
  S_FIELD_ROW_DESC,
  S_FIELD_ROW_HEAD,
  S_FIELD_ROW_LABEL_BASE,
  S_FIELD_ROW_REQUIRED_BADGE,
  S_FIELD_TIP_CARD_BLOCK,
  S_FIELD_TIP_CARD_BLOCK_LABEL,
  S_FIELD_TIP_CARD_COMMANDS_LABEL,
  S_RUNTIME_HELP_TEXT,
  S_RUNTIME_PICKER_WRAP,
  S_SCRIPT_VIEW_MESSAGE_BASE,
  S_SECTION_LABEL,
  S_SECTION_LABEL_SMALL,
  S_SOURCE_UPLOAD_STATUS_LINE_BASE,
  S_SOURCE_URL_STATUS_BASE,
  S_STATUS_BADGE_SM_BASE,
  S_TEXT_MUTED_11,
} from "./constants/theme";
import { AppProvider } from "./context";
import { PageArchive as ArchivePage } from "./features/archive/PageArchive";
import type { DepGroup } from "./features/dependencies/dependencyParser";
import {
  computeEvaluateLevelFromFiles,
  ECO_META,
  PIN_META,
  scanDependencies,
} from "./features/dependencies/dependencyParser";
import { ActionBtn, NavEntryButton } from "./features/explorer/ExplorerNav";
import { ReviewerPreviewOverlay } from "./features/explorer/ReviewerPreviewOverlay";
import {
  allFilePaths,
  defaultScriptTemplates,
  type ExplorerScreensUi,
  findFileByPath,
  PageBuildRuntime,
  PageEvaluate,
  PageGenerateSBOM,
  PageMetadataEntry,
  PageSourceRepoEntry,
  PageTestActivation,
  type ServicePageProps,
} from "./features/explorer/screens";
import { makeLogs } from "./features/explorer/services/logGenerator";
import { missingRequirements } from "./features/explorer/utils/requirements";
import { PageFiles as FilesPage } from "./features/files/PageFiles";
import { LandingView } from "./features/landing/LandingView";
import { PageOverview } from "./features/overview/PageOverview";
import { PodWidget } from "./features/overview/PodWidget";
import { ReviewerView as ReviewerFeatureView } from "./features/reviewer/ReviewerView";
import { REACTIVATION_STEPS } from "./features/reviewer/reviewerSupport";
import { AppRoutes } from "./pages";
import {
  cloneDummyWorkspaceTree,
  createInMemoryDummyWorkspaceService,
  MOCK_FILES,
  makeDummyWorkspaceFromArchiveUpload,
  makeDummyWorkspaceFromOrigin,
} from "./services/dummyWorkspaceService";
import type {
  IWorkspaceService,
  LogEntry as WorkspaceServiceLogEntry,
} from "./services/workspaceService";
import type {
  ActionStates,
  AppPage,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Level,
  LogEntry,
  LogLine,
  Ree,
  RequirementsBannerProps,
  ServiceBadge,
  ServiceLogs,
  ServiceParams,
  SourceUploadCommit,
  StepState,
  Timestamps,
  ToastState,
} from "./types";
import {
  buildCurrentReeArchiveEntries,
  buildZipBlob,
  normalizeSnapshotArchiveName,
  normalizeWorkspacePath,
  reeArchiveEntriesToFiles,
  triggerOnEnterOrSpace,
} from "./utils";
import { fileType } from "./utils/formatting";

type LogLineType = LogLine["type"];

// ── Page keys ─────────────────────────────────────────────────────────────────
// Single source of truth for page/navigation string literals.
// Using these constants instead of raw strings lets TypeScript catch typos
// and makes refactoring (renaming a page) a one-line change.

// ── Mock data is now in services/dummyWorkspaceService.ts ─────────────────────

const DEMO_REE: Ree = {
  name: "genomics-pipeline-v2",
  swhid: "",
  origin_url: "https://github.com/lab/genomics-pipeline",
  source_type: "git",
  detected_dependencies: "",
  repro_level: "",
  runtime: "",
  build_runtime_script: "build_runtime.sh",
  sbom: "",
  activation_script: "activation_test.sh",
  hardware_description: {
    arch: "x86_64",
    memory: "16 GB",
    os: "Debian Bookworm",
    cpu: "Intel Xeon E5-2680",
  },
  _sourceAvailable: false,
  _sourceIncluded: true,
};

const SEALED_DEMO_REE: Ree = {
  ...DEMO_REE,
  swhid: "swh:1:dir:4b825dc642cb6eb9a060e54bf8d69288fbee4904",
  runtime: "runtime.tar.gz",
  sbom: "sbom.spdx.json",
  zenodo_doi: "10.5281/zenodo.1234567",
  _evalLevel: 7,
  _sealedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(), // 3 days ago
  _sealHash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  _sourceIncluded: true,
  _runtimeIncluded: true,
};

// ── Log generation ─────────────────────────────────────────────────────────────
// (moved to features/explorer/services/logGenerator.ts)

// ── Helpers ────────────────────────────────────────────────────────────────────
function upsertWorkspaceFile(nodes: FileTreeNode[], path: string, content: string): FileTreeNode[] {
  const normalizedPath = normalizeWorkspacePath(path);
  const name = normalizedPath.split("/").pop() || normalizedPath || "file.txt";
  const updatedFile: FileTreeNode = {
    id: `vf-${normalizedPath || name}`,
    name,
    type: "file",
    tag: PAGE.SOURCE,
    content,
  };
  return [...nodes.filter((node) => !(node.type === "file" && node.name === name)), updatedFile];
}

// ── Formatting helpers ────────────────────────────────────────────────────────────
// (moved to utils/formatting.ts)

// ── CSS ────────────────────────────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
  @keyframes spin    { to { transform: rotate(360deg); } }
  @keyframes fadeUp  { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
  @keyframes slideIn { from { opacity:0; transform:translateX(10px); } to { opacity:1; transform:translateX(0); } }
  @keyframes pulseGlow { 0%,100% { box-shadow: 0 0 0 0 currentColor; } 50% { box-shadow: 0 0 0 4px transparent; } }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family: Inter, system-ui, sans-serif; background: #f4f6f9; }
  ::-webkit-scrollbar { width:4px; height:4px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:#c4cdd9; border-radius:99px; }
  ::-webkit-scrollbar-thumb:hover { background:#8896a5; }
  input, select, button, textarea { font-family:inherit; outline:none; }
  input:focus, select:focus { border-color:#2563eb !important; box-shadow:0 0 0 3px #2563eb18 !important; }
  .nav-item { transition: background 0.12s, color 0.12s; }
`;

// ── Shared components ──────────────────────────────────────────────────────────
// ── File tree ──────────────────────────────────────────────────────────────────
// ── SBOM contract helpers ──────────────────────────────────────────────────────
// ── ScriptPanel — script viewer + write panel with default templates ───────────
// scriptKind: "build" | "validate" | null (view-only)
// fieldKey: which ree field holds the script path
// files / onFilesChange: virtual repo file tree
// onReeChange: callback to update ree fields (e.g. set the script path)
interface ScriptPanelProps {
  scriptKind: "build" | "validate" | null;
  fieldKey: keyof Ree;
  files: FileTreeNode[];
  onFilesChange?: (files: FileTreeNode[]) => void;
  ree: Ree;
  onReeChange?: (ree: Ree) => void;
  onTemplateSuggestedOutput?: (output: string) => void;
  reviewerMode?: boolean;
  saveToWorkspaceOnly?: boolean;
}
function ScriptPanel({
  scriptKind,
  fieldKey,
  files,
  onFilesChange,
  ree,
  onReeChange,
  onTemplateSuggestedOutput,
  reviewerMode,
  saveToWorkspaceOnly = false,
}: ScriptPanelProps) {
  const scriptPath = (ree[fieldKey] as string) || "";
  const existingFile = scriptPath ? findFileByPath(files, scriptPath) : null;
  const hasScript = !!existingFile;

  // Detect origin type from origin_url
  const originUrl = ree.origin_url || "";
  const isGitHub = /github\.com/i.test(originUrl);
  const isGitLab = /gitlab\.com|gitlab\./i.test(originUrl);
  const isRemoteGit = (isGitHub || isGitLab) && !saveToWorkspaceOnly;

  // view | write
  type ScriptPanelMode = "view" | "write";
  const [mode, setMode] = useState<ScriptPanelMode>(
    hasScript ? "view" : scriptKind ? "write" : "view",
  );
  const [editorContent, setEditorContent] = useState(() => existingFile?.content || "");
  const [editorFilename, setEditorFilename] = useState(
    scriptPath || (scriptKind === "validate" ? "activation_test.sh" : "build_runtime.sh"),
  );
  const [collapsed, setCollapsed] = useState(false);
  const runtimeHint = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const templates = useMemo(
    () => defaultScriptTemplates(scriptKind, runtimeHint),
    [scriptKind, runtimeHint],
  );
  const [templateKey, setTemplateKey] = useState(() => templates[0]?.key || "");

  useEffect(() => {
    if (!templates.length) {
      setTemplateKey("");
      return;
    }
    if (!templates.some((t) => t.key === templateKey)) setTemplateKey(templates[0].key);
  }, [templates, templateKey]);

  const handleModeChange = (m: "view" | "write") => {
    if (m === "write") {
      const f = scriptPath ? findFileByPath(files, scriptPath) : null;
      setEditorContent(f?.content || editorContent);
      setEditorFilename(scriptPath || editorFilename);
    }
    setMode(m);
    setCollapsed(false);
  };

  const commitFile = (fname: string, content: string) => {
    const newFile: FileTreeNode = {
      id: `vf-${fname}`,
      name: fname,
      type: "file",
      tag: PAGE.SOURCE,
      content,
    };
    const updated = [...files.filter((f) => f.name !== fname), newFile];
    onFilesChange?.(updated);
    onReeChange?.({ ...ree, [fieldKey]: fname });
  };

  const handleSave = () => {
    const fname =
      editorFilename.trim() ||
      (scriptKind === "validate" ? "activation_test.sh" : "build_runtime.sh");
    commitFile(fname, editorContent);
    setMode("view");
  };

  const handleUseTemplate = () => {
    const selected = templates.find((t) => t.key === templateKey);
    if (!selected) return;
    setEditorFilename(scriptPath || selected.filename);
    setEditorContent(selected.content);
    if (scriptKind === "build" && selected.suggestedOutput) {
      onTemplateSuggestedOutput?.(selected.suggestedOutput);
    }
  };

  const ftype = fileType(scriptPath || editorFilename);
  const typeStyle = FILE_TYPE_COLORS[ftype] || FILE_TYPE_COLORS.text;
  const viewLines = existingFile ? (existingFile.content || "").split("\n") : null;

  const TABS: Array<{ key: ScriptPanelMode; label: string; icon: (s?: number) => JSX.Element }> = [
    ...(hasScript ? [{ key: "view" as ScriptPanelMode, label: scriptPath, icon: Ic.file }] : []),
    ...(!reviewerMode && scriptKind
      ? [
          {
            key: "write" as ScriptPanelMode,
            label: hasScript ? "Edit" : "Write",
            icon: Ic.terminal,
          },
        ]
      : []),
  ];
  const tabBg: Record<ScriptPanelMode, string> = { view: "#f0fdf4", write: "#f5f3ff" };
  const tabAccent: Record<ScriptPanelMode, string> = { view: "#16a34a", write: "#7c3aed" };

  return (
    <div
      style={{
        border: `1.5px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
        marginBottom: 20,
        background: C.surface,
      }}
    >
      {/* Tab bar */}
      <div
        style={{
          ...{
            display: "flex",
            alignItems: "center",
            background: C.surfaceAlt,
          },
          borderBottom: collapsed && mode === "view" ? "none" : `1px solid ${C.border}`,
        }}
      >
        <div
          style={{
            display: "flex",
            flex: 1,
            overflow: "hidden",
          }}
        >
          {TABS.map((t) => {
            const isActive = mode === t.key;
            const acc = tabAccent[t.key];
            return (
              <button
                type="button"
                key={t.key}
                onClick={() => handleModeChange(t.key)}
                style={{
                  ...{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "8px 14px",
                    border: "none",
                    cursor: "pointer",
                    transition: "background 0.13s",
                    flexShrink: 0,
                  },
                  background: isActive ? tabBg[t.key] : "transparent",
                  borderRight: `1px solid ${C.border}`,
                  borderBottom: isActive ? `2px solid ${acc}` : "2px solid transparent",
                }}
                {...hoverIf(!isActive, hoverBg(`${C.border}40`, "transparent"))}
              >
                <span
                  style={{
                    ...{
                      display: "flex",
                    },
                    color: isActive ? acc : C.textMuted,
                  }}
                >
                  {t.icon(12)}
                </span>
                <span
                  style={{
                    ...{
                      fontSize: 12,
                      whiteSpace: "nowrap",
                    },
                    fontFamily: t.key === "view" ? F.mono : F.sans,
                    color: isActive ? acc : C.textMid,
                    fontWeight: isActive ? 600 : 400,
                  }}
                >
                  {t.label}
                </span>
                {t.key === "view" && (
                  <span
                    style={{
                      ...{
                        fontSize: 9,
                        fontWeight: 700,
                        fontFamily: F.mono,
                        letterSpacing: 0.6,
                        textTransform: "uppercase",
                        padding: "1px 4px",
                        borderRadius: 3,
                        marginLeft: 2,
                      },
                      background: typeStyle.bg,
                      color: typeStyle.color,
                      border: `1px solid ${typeStyle.border}`,
                    }}
                  >
                    {typeStyle.label}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {/* Right: collapse toggle (view mode only) */}
        {mode === "view" && (
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "8px 12px",
              color: C.textMuted,
              display: "flex",
              alignItems: "center",
            }}
            {...hoverColor(C.textMid, C.textMuted)}
          >
            {collapsed ? Ic.chevD(13) : Ic.chevR(13)}
          </button>
        )}
      </div>

      {/* Panel body */}
      {!(collapsed && mode === "view") && (
        <>
          {/* VIEW: read-only light code display */}
          {mode === "view" && (
            <div
              style={{
                background: C.surfaceAlt,
              }}
            >
              {viewLines === null ? (
                <div
                  style={{
                    ...S_SCRIPT_VIEW_MESSAGE_BASE,
                    color: "#f97316",
                  }}
                >
                  File not found in repository tree — check the path in metadata fields.
                </div>
              ) : viewLines.length === 0 ? (
                <div
                  style={{
                    ...S_SCRIPT_VIEW_MESSAGE_BASE,
                    color: C.textMuted,
                    fontStyle: "italic",
                  }}
                >
                  (empty file)
                </div>
              ) : (
                <div
                  style={{
                    padding: "8px 0 10px",
                  }}
                >
                  {(() => {
                    let lineNumber = 0;
                    const seenLines = new Map<string, number>();
                    return viewLines.map((line) => {
                      lineNumber += 1;
                      const occurrence = (seenLines.get(line) ?? 0) + 1;
                      seenLines.set(line, occurrence);
                      return (
                        <div
                          key={`${line}::${occurrence}`}
                          style={{
                            display: "flex",
                            alignItems: "baseline",
                          }}
                        >
                          <span
                            style={{
                              display: "inline-block",
                              minWidth: 40,
                              textAlign: "right",
                              paddingRight: 16,
                              paddingLeft: 12,
                              fontSize: 11,
                              fontFamily: F.mono,
                              color: C.borderMid,
                              userSelect: "none",
                              flexShrink: 0,
                            }}
                          >
                            {lineNumber}
                          </span>
                          <span
                            style={{
                              ...{
                                fontSize: 12,
                                fontFamily: F.mono,
                                lineHeight: 1.75,
                                whiteSpace: "pre",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                display: "block",
                                paddingRight: 16,
                              },
                              color: line.startsWith("#")
                                ? "#94a3b8"
                                : /^(FROM|RUN|COPY|CMD|WORKDIR|ARG|ENV)\b/.test(line)
                                  ? "#0369a1"
                                  : /^(set |echo |docker |pip |apt-get )/.test(line)
                                    ? "#15803d"
                                    : line.includes("=") &&
                                        !line.startsWith(" ") &&
                                        !line.includes("==")
                                      ? "#b45309"
                                      : C.text,
                            }}
                          >
                            {line || " "}
                          </span>
                        </div>
                      );
                    });
                  })()}
                </div>
              )}
            </div>
          )}

          {/* WRITE: editor with default templates in toolbar */}
          {mode === "write" && (
            <div>
              {/* Toolbar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  borderBottom: `1px solid ${C.border}`,
                  background: C.surfaceAlt,
                }}
              >
                {/* Filename */}
                <span
                  style={{
                    color: C.textMuted,
                    display: "flex",
                    flexShrink: 0,
                  }}
                >
                  {Ic.terminal(11)}
                </span>
                <input
                  value={editorFilename}
                  onChange={(event) => setEditorFilename(event.target.value)}
                  placeholder="filename.sh"
                  style={{
                    flex: 1,
                    border: "none",
                    background: "transparent",
                    fontSize: 12,
                    fontFamily: F.mono,
                    color: C.textMid,
                    outline: "none",
                    minWidth: 0,
                  }}
                />

                {/* Template selector */}
                {templates.length > 0 && (
                  <>
                    <select
                      value={templateKey}
                      onChange={(event) => setTemplateKey(event.target.value)}
                      style={{
                        border: `1.5px solid ${C.border}`,
                        borderRadius: 5,
                        padding: "4px 8px",
                        fontSize: 11,
                        fontFamily: F.sans,
                        color: C.textMid,
                        background: C.surface,
                      }}
                    >
                      {templates.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleUseTemplate}
                      title="Insert selected template into editor"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "4px 10px",
                        borderRadius: 5,
                        cursor: "pointer",
                        border: `1px solid ${C.border}`,
                        background: C.surface,
                        color: C.textMid,
                        fontSize: 11,
                        fontWeight: 600,
                        fontFamily: F.sans,
                        transition: "all 0.13s",
                        flexShrink: 0,
                        whiteSpace: "nowrap",
                      }}
                      {...hoverBg(C.surfaceAlt, C.surface)}
                    >
                      {Ic.plus(12)} Apply template
                    </button>
                  </>
                )}

                <div
                  style={{
                    width: 1,
                    height: 16,
                    background: C.border,
                    flexShrink: 0,
                  }}
                />

                {/* Save action */}
                {
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!editorContent.trim()}
                    style={{
                      ...{
                        display: "flex",
                        alignItems: "center",
                        gap: 5,
                        padding: "4px 10px",
                        borderRadius: 5,
                        border: `1px solid ${C.accentBorder}`,
                        background: C.accentBg,
                        fontSize: 11,
                        fontWeight: 600,
                        fontFamily: F.sans,
                        color: C.accent,
                        transition: "all 0.13s",
                        flexShrink: 0,
                        whiteSpace: "nowrap",
                      },
                      cursor: !editorContent.trim() ? "default" : "pointer",
                      opacity: !editorContent.trim() ? 0.4 : 1,
                    }}
                    {...hoverIf(!!editorContent.trim(), hoverBg("#dbeafe", C.accentBg))}
                  >
                    {Ic.check(11)} Save to workspace
                  </button>
                }
              </div>

              {/* Editor area */}
              <textarea
                value={editorContent}
                onChange={(event) => setEditorContent(event.target.value)}
                placeholder={"#!/bin/bash\nset -euo pipefail\n\n# Write your script here..."}
                spellCheck={false}
                style={{
                  width: "100%",
                  minHeight: 200,
                  padding: "10px 14px",
                  fontFamily: F.mono,
                  fontSize: 12,
                  lineHeight: 1.7,
                  color: C.text,
                  background: C.surface,
                  border: "none",
                  resize: "vertical",
                  outline: "none",
                  tabSize: 2,
                  display: "block",
                }}
                onKeyDown={(event) => {
                  if (event.key === "Tab") {
                    event.preventDefault();
                    const target = event.currentTarget;
                    const selectionStart = target.selectionStart;
                    const selectionEnd = target.selectionEnd;
                    setEditorContent(
                      `${editorContent.slice(0, selectionStart)}  ${editorContent.slice(selectionEnd)}`,
                    );
                    requestAnimationFrame(() => {
                      target.selectionStart = target.selectionEnd = selectionStart + 2;
                    });
                  }
                }}
              />

              {/* Status bar */}
              <div
                style={{
                  padding: "5px 12px",
                  background: C.surfaceAlt,
                  borderTop: `1px solid ${C.border}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: F.mono,
                    color: C.textMuted,
                  }}
                >
                  {editorContent.split("\n").length} lines · Tab = 2 spaces
                </span>
                {isRemoteGit && (
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: F.sans,
                      color: C.textMuted,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    {Ic.link(10)}
                    <span>{isGitHub ? "github.com" : "gitlab.com"} · changes go via PR</span>
                  </span>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── File picker input ──────────────────────────────────────────────────────────
interface FileTypeStyle {
  color: string;
  bg: string;
  border: string;
  label: string;
}
const FILE_TYPE_COLORS: Record<string, FileTypeStyle> = {
  shell: { color: "#16a34a", bg: "#f0fdf4", border: "#bbf7d0", label: "sh" },
  dockerfile: { color: "#0891b2", bg: "#ecfeff", border: "#a5f3fc", label: "container" },
  json: { color: "#7c3aed", bg: "#f5f3ff", border: "#ddd6fe", label: "json" },
  python: { color: "#2563eb", bg: "#eff6ff", border: "#bfdbfe", label: "py" },
  nix: { color: "#e4572e", bg: "#fff7f5", border: "#fbd0c4", label: "nix" },
  markdown: { color: "#64748b", bg: "#f8fafc", border: "#e2e8f0", label: "md" },
  config: { color: "#b45309", bg: "#fffbeb", border: "#fde68a", label: "cfg" },
  text: { color: "#475569", bg: "#f8fafc", border: "#e2e8f0", label: "txt" },
};

const PREVIEW_LINES = 6; // how many lines of content to show in the peek

interface FilePickerProps {
  value: string;
  onChange: (value: string) => void;
  files: FileTreeNode[];
  placeholder?: string;
  disabled?: boolean;
  onFocus?: () => void;
  filterFn?: (path: string) => boolean;
}
function FilePicker({
  value,
  onChange,
  files,
  placeholder,
  disabled,
  onFocus,
  filterFn,
}: FilePickerProps) {
  const [open, setOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  // Internal draft: allows the user to type freely; only committed to parent when valid
  const [draft, setDraft] = useState(value || "");

  // Sync draft when parent value changes externally (e.g. cleared by another action)
  const prevValue = useRef(value);
  if (prevValue.current !== value) {
    const old = prevValue.current;
    prevValue.current = value;
    // Only reset draft if user isn't mid-edit on something different
    setDraft((d) => (d === old ? value || "" : d));
  }

  const allPaths = allFilePaths(files);
  const paths = filterFn ? allPaths.filter(filterFn) : allPaths;

  const trimmedDraft = draft.trim();
  const matchedFile = trimmedDraft ? findFileByPath(files, trimmedDraft) : null;
  const notFound = trimmedDraft.length > 0 && !matchedFile;
  // Format violation: either file exists with wrong format, or extension clearly wrong
  const wrongFormat = filterFn && trimmedDraft.length > 0 && !filterFn(trimmedDraft);
  const ftype = fileType(trimmedDraft);
  const typeStyle = FILE_TYPE_COLORS[ftype] || FILE_TYPE_COLORS.text;

  // Derive preview lines from the matched file's content
  const previewLines = matchedFile
    ? (matchedFile.content || "").split("\n").slice(0, PREVIEW_LINES)
    : [];
  const hasMore = matchedFile
    ? (matchedFile.content || "").split("\n").length > PREVIEW_LINES
    : false;

  const isValid = matchedFile && !wrongFormat;

  // Border color reflects validation state
  const borderColor = notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.border;

  const handleDraftChange = (raw: string) => {
    setDraft(raw);
    setPreviewOpen(false);
    const trimmed = raw.trim();
    // Always allow clearing the field
    if (!trimmed) {
      onChange("");
      return;
    }
    const file = trimmed ? findFileByPath(files, trimmed) : null;
    const passesFormat = !filterFn || filterFn(trimmed);
    // Propagate valid value, or clear to empty if invalid
    onChange(file && passesFormat ? trimmed : "");
  };

  const handleSelect = (p: string) => {
    setDraft(p);
    setOpen(false);
    setPreviewOpen(true);
    // Dropdown only shows filtered paths, so always valid
    onChange(p);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 0,
      }}
    >
      {/* Input row */}
      <div
        style={{
          position: "relative",
        }}
      >
        <div
          style={{
            ...{
              display: "flex",
              overflow: "hidden",
              transition: "border-color 0.2s",
            },
            border: `1.5px solid ${borderColor}`,
            borderRadius: isValid && previewOpen ? "7px 7px 0 0" : "7px",
            background: disabled ? C.surfaceAlt : C.surface,
            boxShadow: isValid
              ? `0 0 0 3px #22c55e10`
              : notFound || wrongFormat
                ? `0 0 0 3px #f9731610`
                : "none",
          }}
        >
          {/* Status indicator left of input */}
          <div
            style={{
              ...{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "0 8px 0 10px",
                flexShrink: 0,
                transition: "color 0.2s",
              },
              color: notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.textMuted,
            }}
          >
            {notFound || wrongFormat ? (
              <Svg
                size={14}
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              />
            ) : isValid ? (
              Ic.check(14)
            ) : (
              Ic.file(14)
            )}
          </div>

          <input
            value={draft}
            onChange={(event) => handleDraftChange(event.target.value)}
            disabled={disabled}
            placeholder={placeholder || "path/to/file"}
            onFocus={onFocus}
            style={{
              flex: 1,
              border: "none",
              padding: "7px 4px 7px 0",
              fontSize: 14,
              fontFamily: F.mono,
              color: C.text,
              background: "transparent",
            }}
          />

          {/* Type badge — shown when file is matched */}
          {isValid && (
            <div
              style={{
                ...{
                  display: "flex",
                  alignItems: "center",
                  padding: "0 8px",
                  flexShrink: 0,
                },
                borderLeft: `1px solid ${typeStyle.border}`,
                background: typeStyle.bg,
              }}
            >
              <span
                style={{
                  ...{
                    fontSize: 10,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    letterSpacing: 0.5,
                    textTransform: "uppercase",
                  },
                  color: typeStyle.color,
                }}
              >
                {typeStyle.label}
              </span>
            </div>
          )}

          {/* Peek toggle — shown when file is matched */}
          {isValid && !disabled && (
            <button
              type="button"
              onClick={() => setPreviewOpen((o) => !o)}
              title={previewOpen ? "Hide preview" : "Peek at file contents"}
              style={{
                ...{
                  border: "none",
                  padding: "7px 9px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 11,
                  fontFamily: F.sans,
                  fontWeight: 600,
                  transition: "background 0.15s, color 0.15s",
                  flexShrink: 0,
                },
                background: previewOpen ? "#f0fdf4" : C.surfaceAlt,
                borderLeft: `1px solid ${previewOpen ? "#bbf7d0" : C.border}`,
                color: previewOpen ? "#16a34a" : C.textMid,
              }}
              {...hoverIf(!previewOpen, hoverBg(C.accentBg, C.surfaceAlt))}
              {...hoverIf(!previewOpen, hoverColor(C.accent, C.textMid))}
            >
              {Ic.terminal(13)}
              <span
                style={{
                  display: "none",
                }}
              >
                {previewOpen ? "hide" : "peek"}
              </span>
            </button>
          )}

          {/* Browse button */}
          {!disabled && (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              title="Browse repository files"
              style={{
                ...{
                  border: "none",
                  padding: "7px 9px",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  transition: "background 0.15s, color 0.15s",
                },
                background: open ? C.accentBg : C.surfaceAlt,
                borderLeft: `1px solid ${C.border}`,
                color: open ? C.accent : C.textMid,
              }}
              {...hoverIf(!open, hoverBg(C.accentBg, C.surfaceAlt))}
              {...hoverIf(!open, hoverColor(C.accent, C.textMid))}
            >
              {Ic.folder()}
            </button>
          )}
        </div>

        {/* Browse dropdown */}
        {open && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              zIndex: 50,
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
              maxHeight: 180,
              overflowY: "auto",
            }}
          >
            {paths.length === 0 ? (
              <div
                style={{
                  padding: "12px",
                  fontSize: 13,
                  color: C.textMuted,
                  fontFamily: F.sans,
                  textAlign: "center",
                }}
              >
                {filterFn ? "No matching files in repository" : "No files in repository"}
              </div>
            ) : (
              paths.map((p) => (
                <button
                  type="button"
                  key={p}
                  onClick={() => handleSelect(p)}
                  style={{
                    ...{
                      padding: "7px 12px",
                      fontSize: 13,
                      fontFamily: F.mono,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      border: "none",
                      textAlign: "left",
                      width: "100%",
                    },
                    background: draft === p ? C.accentBg : "transparent",
                    color: draft === p ? C.accent : C.textMid,
                  }}
                  {...hoverIf(draft !== p, hoverBg(C.surfaceAlt, "transparent"))}
                >
                  <span
                    style={{
                      display: "flex",
                      opacity: 0.5,
                    }}
                  >
                    {Ic.file(12)}
                  </span>
                  {p}
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {/* Not-found / wrong-format warning strip */}
      {(notFound || wrongFormat) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 10px",
            background: "#fff7ed",
            border: "1px solid #fed7aa",
            borderTop: "none",
            borderRadius: "0 0 6px 6px",
            animation: "fadeUp 0.15s ease",
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: "#c2410c",
              fontFamily: F.sans,
            }}
          >
            {wrongFormat && notFound
              ? `Wrong format — expected ${placeholder || "the required format"}. File not found either.`
              : wrongFormat
                ? `Wrong format — this field only accepts ${placeholder || "the required format"}. Field not saved.`
                : "File not found in repository — field not saved until the path resolves."}
          </span>
        </div>
      )}

      {/* Inline file preview panel */}
      {isValid && previewOpen && (
        <div
          style={{
            border: "1.5px solid #22c55e",
            borderTop: "none",
            borderRadius: "0 0 7px 7px",
            background: C.surfaceAlt,
            overflow: "hidden",
            animation: "fadeUp 0.15s ease",
          }}
        >
          {/* Preview header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "5px 12px",
              borderBottom: `1px solid ${C.border}`,
              background: C.surface,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
              }}
            >
              <span
                style={{
                  display: "flex",
                  color: "#16a34a",
                  opacity: 0.9,
                }}
              >
                {Ic.file(12)}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: C.textMid,
                  letterSpacing: 0.3,
                }}
              >
                {trimmedDraft}
              </span>
              <span
                style={{
                  ...{
                    fontSize: 9,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    letterSpacing: 0.8,
                    textTransform: "uppercase",
                    padding: "1px 5px",
                    borderRadius: 3,
                  },
                  background: typeStyle.bg,
                  color: typeStyle.color,
                  border: `1px solid ${typeStyle.border}`,
                }}
              >
                {typeStyle.label}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setPreviewOpen(false)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.textMuted,
                display: "flex",
                padding: "2px",
                borderRadius: 3,
              }}
              {...hoverColor(C.textMid, C.textMuted)}
            >
              {Ic.x(12)}
            </button>
          </div>

          {/* Code lines */}
          <div
            style={{
              padding: "8px 0 6px",
            }}
          >
            {(() => {
              let lineNumber = 0;
              const seenLines = new Map<string, number>();
              return previewLines.map((line) => {
                lineNumber += 1;
                const occurrence = (seenLines.get(line) ?? 0) + 1;
                seenLines.set(line, occurrence);
                return (
                  <div
                    key={`${line}::${occurrence}`}
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 0,
                    }}
                  >
                    <span
                      style={{
                        display: "inline-block",
                        minWidth: 36,
                        textAlign: "right",
                        paddingRight: 14,
                        paddingLeft: 12,
                        fontSize: 11,
                        fontFamily: F.mono,
                        color: C.borderMid,
                        userSelect: "none",
                        flexShrink: 0,
                      }}
                    >
                      {lineNumber}
                    </span>
                    <span
                      style={{
                        ...{
                          fontSize: 12,
                          fontFamily: F.mono,
                          lineHeight: 1.7,
                          whiteSpace: "pre",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "block",
                          paddingRight: 14,
                        },
                        color: line.startsWith("#")
                          ? "#94a3b8"
                          : line.startsWith("FROM") ||
                              line.startsWith("RUN") ||
                              line.startsWith("COPY") ||
                              line.startsWith("CMD") ||
                              line.startsWith("WORKDIR")
                            ? "#0369a1"
                            : line.startsWith("set ") ||
                                line.startsWith("echo ") ||
                                line.startsWith("docker ")
                              ? "#15803d"
                              : line.includes("=") && !line.includes("==")
                                ? "#b45309"
                                : C.text,
                      }}
                    >
                      {line || " "}
                    </span>
                  </div>
                );
              });
            })()}
            {hasMore && (
              <div
                style={{
                  padding: "4px 12px 2px 36px",
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: C.textMuted,
                  fontStyle: "italic",
                }}
              >
                … {(matchedFile.content || "").split("\n").length - PREVIEW_LINES} more lines
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Form helpers ───────────────────────────────────────────────────────────────
const inp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

// ── Log view ───────────────────────────────────────────────────────────────────
interface LogStyleEntry {
  pre: string;
  color: string;
  bg: string;
}
const LOG_STYLE: Record<LogLineType, LogStyleEntry> = {
  info: { pre: "  INFO", color: "#475569", bg: "transparent" },
  ok: { pre: "    OK", color: "#16a34a", bg: "#f0fdf4" },
  warn: { pre: "  WARN", color: "#d97706", bg: "#fef3c7" },
  err: { pre: "   ERR", color: "#dc2626", bg: "#fef2f2" },
  out: { pre: "      ", color: "#1e293b", bg: "transparent" },
};

interface LogPanelProps {
  log: LogEntry | null;
  running?: boolean;
}
function LogPanel({ log }: LogPanelProps) {
  return (
    <div
      style={{
        flex: 1,
        overflow: "auto",
        background: "#f8fafc",
        borderRadius: 10,
        border: `1px solid ${C.border}`,
        minHeight: 200,
      }}
    >
      {!log ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            minHeight: 200,
            gap: 8,
            color: C.textMuted,
          }}
        >
          {Ic.terminal()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>No output yet</span>
        </div>
      ) : (
        <div style={{ padding: "12px 0" }}>
          <div
            style={{
              padding: "6px 18px 12px",
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.mono,
              borderBottom: `1px solid ${C.border}`,
              marginBottom: 4,
            }}
          >
            Last run:{" "}
            {new Date(log.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
          </div>
          {(() => {
            const seenLines = new Map<string, number>();
            return log.lines.map((line) => {
              const lineSig = `${line.type}:${line.msg}`;
              const occurrence = (seenLines.get(lineSig) ?? 0) + 1;
              seenLines.set(lineSig, occurrence);
              const s = LOG_STYLE[line.type] || LOG_STYLE.info;
              return (
                <div
                  key={`${lineSig}::${occurrence}`}
                  style={{
                    display: "flex",
                    padding: "3px 18px",
                    background: s.bg,
                    fontFamily: F.mono,
                    fontSize: 13,
                    lineHeight: 1.75,
                  }}
                >
                  <span
                    style={{
                      color: s.color,
                      fontWeight: 600,
                      marginRight: 14,
                      flexShrink: 0,
                      fontSize: 11,
                      opacity: 0.75,
                      minWidth: 52,
                    }}
                  >
                    [{s.pre}]
                  </span>
                  <span style={{ color: s.color }}>{line.msg}</span>
                </div>
              );
            });
          })()}
        </div>
      )}
    </div>
  );
}

// ── Service requirement helpers ───────────────────────────────────────────────────
// (moved to features/explorer/utils/requirements.ts)

function tipTargetChip(active: boolean, idleLabel = "Click for tips"): React.ReactNode {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: F.sans,
        color: active ? C.accent : C.textMuted,
        background: active ? C.accentBg : C.surfaceAlt,
        border: `1px solid ${active ? C.accentBorder : C.border}`,
        borderRadius: 99,
        padding: "1px 7px",
        letterSpacing: 0.2,
      }}
    >
      {Ic.info(10)} {active ? "Tips open" : idleLabel}
    </span>
  );
}

function descToTwoTierTips(desc: string): string[] {
  const text = (desc || "").trim();
  if (!text) return [];
  const firstSentenceEnd = text.indexOf(".");
  if (firstSentenceEnd === -1 || firstSentenceEnd === text.length - 1) return [text];
  const first = text.slice(0, firstSentenceEnd + 1).trim();
  const second = text.slice(firstSentenceEnd + 1).trim();
  return second ? [first, second] : [first];
}

// ── Field row with description ─────────────────────────────────────────────────
interface FieldRowProps {
  fieldKey: string;
  required?: boolean;
  children: React.ReactNode;
  locked?: boolean;
  onFocus?: () => void;
  active?: boolean;
}
function FieldRow({ fieldKey, required, children, locked, onFocus, active }: FieldRowProps) {
  const meta = FIELD_META[fieldKey] || { label: fieldKey, desc: "" };
  const tipEnabled = !!onFocus;
  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: section container intentionally acts as full-surface tip target.
    <div
      id={`field-${fieldKey}`}
      onClick={tipEnabled ? () => onFocus?.() : undefined}
      role={tipEnabled ? "button" : undefined}
      tabIndex={tipEnabled ? 0 : undefined}
      onKeyDown={(event) => {
        if (!tipEnabled) return;
        triggerOnEnterOrSpace(event, () => onFocus?.());
      }}
      style={{
        ...S_FIELD_ROW_BASE,
        background: active ? `${C.accentBg}75` : "transparent",
        cursor: tipEnabled ? "pointer" : "default",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      <div>
        <div style={S_FIELD_ROW_HEAD}>
          <span
            style={{
              ...S_FIELD_ROW_LABEL_BASE,
              color: active ? C.accent : C.text,
            }}
          >
            {meta.label}
          </span>
          {tipEnabled && tipTargetChip(!!active)}
          {required && <span style={S_FIELD_ROW_REQUIRED_BADGE}>required</span>}
          {locked && fieldKey !== "swhid" && (
            <span
              style={{
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
                background: C.surfaceAlt,
                border: `1px solid ${C.border}`,
                borderRadius: 3,
                padding: "1px 4px",
              }}
            >
              locked
            </span>
          )}
        </div>
        <p style={S_FIELD_ROW_DESC}>{meta.desc}</p>
      </div>
      <div style={S_FIELD_ROW_CONTENT}>{children}</div>
    </div>
  );
}

// ── Dashboard field section card ───────────────────────────────────────────────
interface FieldSectionProps {
  title: string;
  icon: React.ReactNode;
  subtitle?: string;
  children: React.ReactNode;
  filledCount: number;
  totalCount: number;
}
function FieldSection({
  title,
  icon,
  subtitle,
  children,
  filledCount,
  totalCount,
}: FieldSectionProps) {
  const allFilled = filledCount === totalCount && totalCount > 0;
  const someFilled = filledCount > 0;
  const pct = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0;
  return (
    <div
      style={{
        ...{
          background: C.surface,
          borderRadius: 10,
          overflow: "hidden",
          transition: "border-color 0.3s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        },
        border: `1px solid ${allFilled ? "#22c55e40" : C.border}`,
      }}
    >
      <div
        style={{
          ...{
            padding: "11px 20px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "background 0.3s",
          },
          borderBottom: `1px solid ${allFilled ? "#22c55e30" : C.border}`,
          background: allFilled ? "#f0fdf4" : "#fafbfd",
        }}
      >
        {/* Accent bar */}
        <div
          style={{
            ...{
              width: 3,
              height: 16,
              borderRadius: 99,
              flexShrink: 0,
              transition: "background 0.3s",
            },
            background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
          }}
        />
        <span
          style={{
            ...{
              display: "flex",
            },
            color: allFilled ? "#16a34a" : C.textMuted,
          }}
        >
          {icon}
        </span>
        <span
          style={{
            ...{
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: 1,
              textTransform: "uppercase",
              fontFamily: F.sans,
            },
            color: allFilled ? "#15803d" : C.text,
          }}
        >
          {title}
        </span>
        {subtitle && (
          <span
            style={{
              fontSize: 12,
              color: C.textMuted,
              fontWeight: 400,
              textTransform: "none",
              letterSpacing: 0,
            }}
          >
            — {subtitle}
          </span>
        )}
        <div
          style={{
            flex: 1,
          }}
        />
        {totalCount > 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <div
              style={{
                width: 40,
                height: 3,
                borderRadius: 99,
                background: C.border,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: allFilled ? "#22c55e" : someFilled ? "#f59e0b" : C.borderMid,
                  borderRadius: 99,
                  transition: "width 0.4s",
                }}
              />
            </div>
            <span
              style={{
                ...{
                  fontSize: 11,
                  fontFamily: F.mono,
                  fontWeight: 600,
                },
                color: allFilled ? "#16a34a" : someFilled ? "#92400e" : C.textMuted,
              }}
            >
              {filledCount}/{totalCount}
            </span>
          </div>
        )}
      </div>
      <div
        style={{
          padding: "0 20px",
        }}
      >
        {children}
      </div>
    </div>
  );
}

// ── Field tip card — shown in sidebar when a field is focused ──────────────────
interface FieldTipCardProps {
  fieldKey: string;
  onDismiss: () => void;
}
function FieldTipCard({ fieldKey, onDismiss }: FieldTipCardProps) {
  const meta = FIELD_META[fieldKey];
  if (!meta) return null;
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
        padding: 16,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: C.accent,
            }}
          />
          <span
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.1,
              color: C.accent,
            }}
          >
            Field guide
          </span>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          style={{
            fontSize: 11,
            fontFamily: F.sans,
            color: C.textMuted,
            background: C.surfaceAlt,
            border: `1px solid ${C.border}`,
            borderRadius: 6,
            padding: "4px 8px",
            cursor: "pointer",
          }}
          {...hoverColor(C.text, C.textMuted)}
        >
          {Ic.x(13)}
        </button>
      </div>

      <div
        style={{
          fontSize: 15,
          fontWeight: 700,
          color: C.text,
          marginBottom: 4,
        }}
      >
        {meta.label}
      </div>
      <p
        style={{
          fontSize: 13,
          color: C.textMid,
          lineHeight: 1.6,
          margin: "0 0 14px",
        }}
      >
        {meta.desc}
      </p>

      {/* Example value */}
      {meta.example && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_BLOCK_LABEL}>Example</div>
          <div
            style={{
              background: C.surfaceAlt,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              padding: "9px 12px",
              fontFamily: F.mono,
              fontSize: 13,
              color: C.accent,
              wordBreak: "break-all",
            }}
          >
            {meta.example}
          </div>
        </div>
      )}

      {/* Format */}
      {meta.format && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_BLOCK_LABEL}>Format</div>
          <p
            style={{
              fontSize: 13,
              color: C.textMid,
              lineHeight: 1.6,
              margin: 0,
              fontFamily: F.mono,
            }}
          >
            {meta.format}
          </p>
        </div>
      )}

      {/* How to */}
      {meta.howTo && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_BLOCK_LABEL}>How to get this</div>
          <pre
            style={{
              ...{
                fontSize: 13,
                color: C.textMid,
                lineHeight: 1.65,
                margin: 0,
                whiteSpace: "pre-wrap",
              },
              fontFamily: meta.howTo.includes("\n") ? F.mono : "inherit",
            }}
          >
            {meta.howTo}
          </pre>
        </div>
      )}

      {/* Tool commands */}
      {meta.toolCommands && meta.toolCommands.length > 0 && (
        <div style={S_FIELD_TIP_CARD_BLOCK}>
          <div style={S_FIELD_TIP_CARD_COMMANDS_LABEL}>Commands</div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {meta.toolCommands.map((tc) => (
              <div key={`${tc.label}:${tc.cmd}`}>
                <div
                  style={{
                    fontSize: 11,
                    color: C.textMuted,
                    fontFamily: F.sans,
                    marginBottom: 4,
                  }}
                >
                  {tc.label}
                </div>
                <div
                  style={{
                    background: "#0f172a",
                    borderRadius: 6,
                    padding: "10px 12px",
                    fontFamily: F.mono,
                    fontSize: 13,
                    color: "#94d2bd",
                    wordBreak: "break-all",
                    lineHeight: 1.6,
                  }}
                >
                  {tc.cmd}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tools / links */}
      {meta.tools && meta.tools.length > 0 && (
        <div>
          <div style={S_FIELD_TIP_CARD_COMMANDS_LABEL}>Tools</div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
            }}
          >
            {meta.tools.map((t) => (
              <a
                key={t.url}
                href={t.url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 13,
                  fontFamily: F.sans,
                  color: C.accent,
                  background: C.accentBg,
                  border: `1px solid ${C.accentBorder}`,
                  borderRadius: 5,
                  padding: "4px 10px",
                  textDecoration: "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                {Ic.link(11)} {t.label}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface FieldTipsSidebarProps {
  focusedField: string | null;
  onFocusField?: (field: string) => void;
  onClear: () => void;
  tipFields?: string[];
  emptyMessage?: string;
  generalTips?: string[];
  generalTitle?: string;
}
function FieldTipsSidebar({
  focusedField,
  onFocusField,
  onClear,
  tipFields,
  emptyMessage,
  generalTips = [],
  generalTitle = "Step Purpose",
}: FieldTipsSidebarProps) {
  const activeField =
    focusedField && (!tipFields || tipFields.includes(focusedField)) ? focusedField : null;
  const showFieldPicker = !!(tipFields && tipFields.length > 0 && onFocusField);
  const emptyText =
    emptyMessage ||
    "Click any field — here or in the status bar above — to see examples, format rules, and commands.";
  const workflowTipFields = (tipFields || []).filter((fieldKey) => !!FIELD_META[fieldKey]);

  return (
    <div
      style={{
        width: 296,
        borderLeft: `1px solid ${C.border}`,
        background: C.surface,
        overflowY: "auto",
        padding: 20,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      {showFieldPicker && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.1,
            }}
          >
            Tips
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
            }}
          >
            {(tipFields || []).map((fieldKey) => {
              const isActive = activeField === fieldKey;
              return (
                <button
                  type="button"
                  key={fieldKey}
                  onClick={() => onFocusField(fieldKey)}
                  style={{
                    ...{
                      fontSize: 11,
                      fontFamily: F.sans,
                      fontWeight: 700,
                      letterSpacing: 0.2,
                      borderRadius: 99,
                      padding: "3px 9px",
                      cursor: "pointer",
                    },
                    color: isActive ? C.accent : C.textMid,
                    background: isActive ? C.accentBg : C.surfaceAlt,
                    border: `1px solid ${isActive ? C.accentBorder : C.border}`,
                  }}
                >
                  {FIELD_META[fieldKey]?.label || fieldKey}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {generalTips.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span
              style={{
                color: C.textMid,
                display: "flex",
              }}
            >
              {Ic.info(13)}
            </span>
            <span
              style={{
                ...S_SECTION_LABEL,
                letterSpacing: 0.8,
                color: C.textMid,
              }}
            >
              {generalTitle}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {generalTips.map((tip) => (
              <p
                key={tip}
                style={{
                  margin: 0,
                  fontSize: 12,
                  color: C.textMid,
                  lineHeight: 1.55,
                }}
              >
                {tip}
              </p>
            ))}
          </div>
        </div>
      )}

      {activeField ? (
        <FieldTipCard fieldKey={activeField} onDismiss={onClear} />
      ) : workflowTipFields.length > 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            padding: "12px 13px",
            background: C.accentBg,
            border: `1px solid ${C.accentBorder}`,
            borderRadius: 9,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span
              style={{
                color: C.accent,
                display: "flex",
              }}
            >
              {Ic.info(13)}
            </span>
            <span
              style={{
                ...S_SECTION_LABEL,
                letterSpacing: 0.8,
                color: C.accent,
              }}
            >
              Workflow tips
            </span>
          </div>
          <p
            style={{
              fontSize: 12,
              color: C.textMid,
              lineHeight: 1.55,
              margin: 0,
            }}
          >
            No field selected. Here are the key tips for this page/workflow:
          </p>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {workflowTipFields.map((fieldKey) => {
              const meta = FIELD_META[fieldKey];
              return (
                <button
                  type="button"
                  key={fieldKey}
                  onClick={() => onFocusField?.(fieldKey)}
                  style={{
                    ...{
                      textAlign: "left",
                      padding: "8px 10px",
                      borderRadius: 8,
                      border: `1px solid ${C.accentBorder}`,
                      background: C.surface,
                      display: "flex",
                      flexDirection: "column",
                      gap: 3,
                    },
                    cursor: onFocusField ? "pointer" : "default",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: C.text,
                      fontFamily: F.sans,
                    }}
                  >
                    {meta?.label || fieldKey}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      color: C.textMuted,
                      lineHeight: 1.45,
                    }}
                  >
                    {meta?.desc || ""}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            padding: "12px 13px",
            background: C.accentBg,
            border: `1px solid ${C.accentBorder}`,
            borderRadius: 9,
          }}
        >
          <span
            style={{
              color: C.accent,
              flexShrink: 0,
              marginTop: 1,
            }}
          >
            {Ic.info(13)}
          </span>
          <p
            style={{
              fontSize: 13,
              color: C.textMid,
              lineHeight: 1.6,
              margin: 0,
            }}
          >
            {emptyText}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Source URL field with draft/commit pattern ─────────────────────────────────
interface SourceUrlFieldProps {
  locked: boolean;
  committedValue: string;
  onCommit: (value: string) => void;
  onFocus?: () => void;
}
function SourceUrlField({ locked, committedValue, onCommit, onFocus }: SourceUrlFieldProps) {
  const [draft, setDraft] = useState(committedValue || "");
  const [checkState, setCheckState] = useState<"idle" | "checking" | "reachable" | "unreachable">(
    "idle",
  );
  const [checkedFor, setCheckedFor] = useState<string>("");

  const prevCommitted = useRef<string | undefined>(committedValue);
  if (prevCommitted.current !== committedValue) {
    prevCommitted.current = committedValue;
    setDraft(committedValue || "");
    if ((committedValue || "") !== checkedFor) {
      setCheckState("idle");
      setCheckedFor("");
    }
  }

  const isDirty = draft.trim() !== (committedValue || "").trim();

  const handleCheckReachable = async () => {
    const candidate = draft.trim();
    if (!candidate) return;
    setCheckState("checking");
    setCheckedFor(candidate);
    await new Promise((resolve) => setTimeout(resolve, 700));
    const reachable = /^https?:\/\/[^\s]+$/i.test(candidate);
    setCheckState(reachable ? "reachable" : "unreachable");
    if (reachable) onCommit(candidate);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "stretch",
        }}
      >
        <div
          style={{
            flex: 1,
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: C.textMuted,
              pointerEvents: "none",
            }}
          >
            {Ic.link()}
          </div>
          <input
            disabled={locked}
            value={draft}
            onChange={(event) => {
              const next = event.target.value;
              setDraft(next);
              if (!next.trim()) {
                onCommit("");
              }
              if (checkedFor && next.trim() !== checkedFor) {
                setCheckState("idle");
                setCheckedFor("");
              }
            }}
            onFocus={onFocus}
            onKeyDown={(event) => {
              if (event.key === "Enter" && draft.trim()) handleCheckReachable();
            }}
            placeholder="https://github.com/org/repo"
            style={{
              ...inp(locked),
              paddingLeft: 32,
              borderColor: isDirty ? "#f59e0b" : undefined,
            }}
          />
        </div>
        <button
          type="button"
          onClick={handleCheckReachable}
          disabled={locked || !draft.trim() || checkState === "checking"}
          style={{
            ...{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 13px",
              borderRadius: 7,
              fontSize: 13,
              fontWeight: 600,
              fontFamily: F.sans,
              flexShrink: 0,
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            },
            cursor: locked || !draft.trim() || checkState === "checking" ? "default" : "pointer",
            border: `1.5px solid ${draft.trim() ? C.accentBorder : C.border}`,
            background: draft.trim() ? C.accentBg : C.surfaceAlt,
            color: draft.trim() ? C.accent : C.textMuted,
            opacity: locked ? 0.5 : 1,
          }}
          {...hoverIf(!locked && !!draft.trim() && checkState !== "checking", hoverBrightness(96))}
        >
          {checkState === "checking" ? Ic.loader(13) : Ic.link(13)} Check reachable
        </button>
      </div>
      {isDirty && draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#92400e" }}>
          {Ic.info(10)} Setting a new source will reset all workflow results.
        </div>
      )}
      {committedValue && !isDirty && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            fontSize: 11,
            fontFamily: F.mono,
            color: "#16a34a",
          }}
        >
          {Ic.check(10)}
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {committedValue}
          </span>
        </div>
      )}
      {checkState === "reachable" && checkedFor === draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#15803d" }}>
          {Ic.check(10)} URL reachable
        </div>
      )}
      {checkState === "unreachable" && checkedFor === draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#b45309" }}>
          {Ic.info(10)} URL not reachable (or invalid format)
        </div>
      )}
    </div>
  );
}

// ── Source upload field with pending confirm ────────────────────────────────────
interface SourceUploadFieldProps {
  locked: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onCommit: (payload: SourceUploadCommit) => void;
  committedName?: string;
}
function SourceUploadField({
  locked,
  disabled = false,
  disabledReason,
  onCommit,
  committedName,
}: SourceUploadFieldProps) {
  const archiveRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState<SourceUploadCommit | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);
  const inputDisabled = locked || disabled;

  const handleArchive = (file: File) => {
    if (!file || inputDisabled) return;
    setDropError(null);
    setPending({ mode: "archive", archiveName: file.name });
  };

  const handleDrop = (dragEvent: React.DragEvent<HTMLElement>) => {
    dragEvent.preventDefault();
    setDragging(false);
    if (inputDisabled) return;
    const files = dragEvent.dataTransfer.files;
    if (!files || files.length === 0) return;
    if (files.length !== 1 || !/\.(zip|tar|tar\.gz|tgz)$/i.test(files[0].name)) {
      setDropError("Only a single tarball/archive upload is allowed for direct repo upload.");
      return;
    }
    handleArchive(files[0]);
  };

  const handleConfirm = () => {
    if (!pending) return;
    onCommit(pending);
    setPending(null);
  };

  const handleCancel = () => setPending(null);

  return (
    <div
      style={{
        padding: "8px 0 14px",
      }}
    >
      <input
        ref={archiveRef}
        type="file"
        accept=".zip,.tar,.gz,.tgz,.tar.gz"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) handleArchive(file);
          event.currentTarget.value = "";
        }}
        style={{
          display: "none",
        }}
      />

      {committedName && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 14px",
            borderRadius: 8,
            background: "#f0fdf4",
            border: "1.5px solid #bbf7d0",
            marginBottom: 8,
          }}
        >
          <span
            style={{
              color: "#16a34a",
              display: "flex",
            }}
          >
            {Ic.archive()}
          </span>
          <span
            style={{
              flex: 1,
              fontSize: 13,
              fontFamily: F.mono,
              color: "#15803d",
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {committedName}
          </span>
          {!locked && (
            <button
              type="button"
              onClick={() => archiveRef.current?.click()}
              disabled={inputDisabled}
              style={{
                background: "none",
                border: `1px solid ${C.border}`,
                borderRadius: 5,
                cursor: "pointer",
                color: C.textMuted,
                fontSize: 11,
                fontFamily: F.sans,
                padding: "2px 8px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
              {...hoverBorderColor(C.accent, C.border)}
              {...hoverColor(C.accent, C.textMuted)}
            >
              {Ic.upload(11)} Replace
            </button>
          )}
        </div>
      )}

      {/* Pending confirmation */}
      {pending && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 5,
            marginBottom: 8,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              borderRadius: 8,
              background: "#fffbeb",
              border: "1.5px solid #f59e0b",
            }}
          >
            <span
              style={{
                color: "#d97706",
                display: "flex",
              }}
            >
              {Ic.archive()}
            </span>
            <span
              style={{
                flex: 1,
                fontSize: 13,
                fontFamily: F.mono,
                color: "#92400e",
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {pending.archiveName}
            </span>
            <button
              type="button"
              onClick={handleConfirm}
              style={{
                background: "#fffbeb",
                border: "1.5px solid #f59e0b",
                borderRadius: 6,
                cursor: "pointer",
                color: "#b45309",
                fontSize: 12,
                fontWeight: 700,
                fontFamily: F.sans,
                padding: "4px 10px",
                display: "flex",
                alignItems: "center",
                gap: 4,
                flexShrink: 0,
              }}
              {...hoverBrightness(96)}
            >
              {Ic.check(11)} Add to workspace
            </button>
            <button
              type="button"
              onClick={handleCancel}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.textMuted,
                display: "flex",
                padding: 2,
                borderRadius: 4,
              }}
              {...hoverColor("#dc2626", C.textMuted)}
            >
              {Ic.x(13)}
            </button>
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#92400e",
              fontFamily: F.sans,
              display: "flex",
              alignItems: "center",
              gap: 4,
              paddingLeft: 2,
            }}
          >
            {Ic.info(10)} Setting a new source will reset all workflow results.
          </div>
        </div>
      )}

      {/* Drop zone — always show if no committed file yet, or for replacement */}
      {!committedName && !pending && (
        <button
          type="button"
          onDragOver={(dragEvent) => {
            dragEvent.preventDefault();
            if (!inputDisabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !inputDisabled && archiveRef.current?.click()}
          disabled={inputDisabled}
          style={{
            ...{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "22px 16px",
              borderRadius: 8,
              transition: "all 0.15s",
              width: "100%",
              appearance: "none",
            },
            cursor: inputDisabled ? "default" : "pointer",
            border: `1.5px dashed ${dragging ? C.accent : C.borderMid}`,
            background: dragging ? C.accentBg : C.bg,
            opacity: inputDisabled ? 0.55 : 1,
          }}
          onMouseEnter={(mouseEvent) => {
            if (!inputDisabled) {
              mouseEvent.currentTarget.style.borderColor = C.accent;
              mouseEvent.currentTarget.style.background = C.accentBg;
            }
          }}
          onMouseLeave={(mouseEvent) => {
            if (!dragging) {
              mouseEvent.currentTarget.style.borderColor = C.borderMid;
              mouseEvent.currentTarget.style.background = C.bg;
            }
          }}
        >
          <span
            style={{
              ...{
                display: "flex",
              },
              color: dragging ? C.accent : C.textMuted,
            }}
          >
            {Ic.upload(18)}
          </span>
          <span
            style={{
              ...{
                fontSize: 13,
                fontFamily: F.sans,
              },
              color: dragging ? C.accent : C.textMid,
            }}
          >
            Drop archive or{" "}
            <span
              style={{
                color: C.accent,
                fontWeight: 600,
              }}
            >
              browse archive
            </span>
          </span>
          <span
            style={{
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.mono,
              marginTop: 4,
            }}
          >
            .zip · .tar · .tar.gz
          </span>
        </button>
      )}

      {disabledReason && (
        <div style={{ ...S_SOURCE_UPLOAD_STATUS_LINE_BASE, color: C.textMuted }}>
          {Ic.info(10)} {disabledReason}
        </div>
      )}

      {dropError && (
        <div style={{ ...S_SOURCE_UPLOAD_STATUS_LINE_BASE, color: "#b45309" }}>
          {Ic.info(10)} {dropError}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RuntimeField — runtime tar.gz field with include/skip toggle
// ══════════════════════════════════════════════════════════════════════════════
interface RuntimeFieldProps {
  locked: boolean;
  ree: Ree;
  onChange: (ree: Ree) => void;
  onFocus?: () => void;
  active?: boolean;
  files: FileTreeNode[];
}
function RuntimeField({ locked, ree, onChange, onFocus, active, files }: RuntimeFieldProps) {
  const val = ree.runtime || "";
  const isSkipped = val === "__skipped__";
  const isTarball = !isSkipped && /\.(tar\.gz|tgz)$/i.test(val);
  const isImageRef = !isSkipped && !!val && !isTarball;
  const mode = isSkipped ? "skip" : isImageRef ? "image" : "tarball";

  const set = (k: string, v: unknown) => onChange({ ...ree, [k]: v });

  const handleModeChange = (m: "tarball" | "image" | "skip") => {
    if (locked) return;
    if (m === "tarball") set("runtime", "");
    if (m === "image") set("runtime", isImageRef ? val : "");
    if (m === "skip") set("runtime", "__skipped__");
  };

  const meta = FIELD_META.runtime;

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: section container intentionally acts as full-surface tip target.
    <div
      id="field-runtime"
      onClick={onFocus ? () => onFocus?.() : undefined}
      role={onFocus ? "button" : undefined}
      tabIndex={onFocus ? 0 : undefined}
      onKeyDown={(event) => {
        if (!onFocus) return;
        triggerOnEnterOrSpace(event, () => onFocus?.());
      }}
      style={{
        ...S_FIELD_ROW_BASE,
        background: active ? `${C.accentBg}75` : "transparent",
        cursor: onFocus ? "pointer" : "default",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      {/* Left: label + description + used-by */}
      <div>
        <div style={S_FIELD_ROW_HEAD}>
          <span
            style={{
              ...S_FIELD_ROW_LABEL_BASE,
              color: active ? C.accent : C.text,
            }}
          >
            {meta.label}
          </span>
          {!!onFocus && tipTargetChip(!!active)}
        </div>
        <p style={S_FIELD_ROW_DESC}>{meta.desc}</p>
      </div>

      {/* Right: mode toggle + input */}
      <div
        style={{
          ...S_FIELD_ROW_CONTENT,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {/* mode toggle: Tarball | Image ref only */}
        <div
          style={{
            display: "flex",
            gap: 5,
          }}
        >
          {(
            [
              { id: "tarball", label: "Tarball", icon: Ic.archive },
              { id: "image", label: "Image ref", icon: Ic.cpu },
            ] as const
          ).map((opt) => {
            const isActive = mode === opt.id || (mode === "skip" && opt.id === "tarball");
            return (
              <button
                type="button"
                key={opt.id}
                onClick={() => handleModeChange(opt.id)}
                disabled={locked}
                style={{
                  ...{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 5,
                    padding: "6px 8px",
                    borderRadius: 7,
                    fontSize: 11,
                    fontWeight: 600,
                    fontFamily: F.sans,
                    transition: "all 0.15s",
                  },
                  cursor: locked ? "default" : "pointer",
                  border: `1.5px solid ${isActive ? C.accent : C.border}`,
                  background: isActive ? C.accentBg : C.surface,
                  color: isActive ? C.accent : C.textMid,
                  opacity: locked ? 0.6 : 1,
                }}
                {...hoverIf(!locked && !isActive, hoverBorderColor(C.borderMid, C.border))}
              >
                <span
                  style={{
                    display: "flex",
                  }}
                >
                  {opt.icon(11)}
                </span>
                {opt.label}
              </button>
            );
          })}
        </div>

        {/* tarball mode: file picker */}
        {(mode === "tarball" || mode === "skip") && (
          <div style={S_RUNTIME_PICKER_WRAP}>
            <FilePicker
              disabled={locked}
              value={isTarball ? val : ""}
              onChange={(v) => set("runtime", v)}
              files={files}
              placeholder="runtime.tar.gz"
              onFocus={onFocus}
              filterFn={(p) => /\.(tar\.gz|tgz)$/i.test(p)}
            />
            <div style={S_RUNTIME_HELP_TEXT}>
              Bundled into the REE archive on deposit. Produced by your build script via{" "}
              <code
                style={{
                  fontFamily: F.mono,
                  fontSize: 10.5,
                  background: C.surfaceAlt,
                  padding: "1px 4px",
                  borderRadius: 3,
                }}
              >
                docker save … | gzip
              </code>
              .
            </div>
            {isSkipped && (
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  padding: "8px 11px",
                  background: "#fff7ed",
                  border: "1px solid #fde68a",
                  borderRadius: 7,
                }}
              >
                <span
                  style={{
                    color: "#d97706",
                    display: "flex",
                    flexShrink: 0,
                    marginTop: 1,
                  }}
                >
                  {Ic.info(12)}
                </span>
                <div
                  style={{
                    fontSize: 11,
                    color: "#92400e",
                    lineHeight: 1.5,
                  }}
                >
                  Tarball will <strong>not</strong> be bundled in the REE archive. Ensure it is
                  reproducible from the build script alone.
                </div>
              </div>
            )}
          </div>
        )}

        {/* image ref mode: free text */}
        {mode === "image" && (
          <div style={S_RUNTIME_PICKER_WRAP}>
            <input
              disabled={locked}
              value={isImageRef ? val : ""}
              onChange={(event) => set("runtime", event.target.value)}
              onFocus={onFocus}
              placeholder="ree:latest  or  sha256:abc123…"
              style={inp(locked)}
            />
            <div style={S_RUNTIME_HELP_TEXT}>
              A Docker/Podman image name or digest. Not bundled in the REE — the image must be
              rebuilt from the build script. Used by the SBOM step as the syft scan target.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Next-step nudge — contextual "what to do next" banner ────────────────────
// stepKey: current page key; badges: completed badge map; onGo: navigate fn
interface NextStepNudgeProps {
  stepKey: string;
  badges: Badges;
  onGo: (key: string) => void;
}
function NextStepNudge({ stepKey, onGo }: NextStepNudgeProps) {
  const STEPS = [
    { key: PAGE.SOURCE, nextKey: PAGE.METADATA, nextLabel: "Provide Metadata", cond: () => true },
    { key: PAGE.METADATA, nextKey: "evaluate", nextLabel: "Evaluate", cond: () => true },
    { key: "evaluate", nextKey: "build", nextLabel: "Build Runtime", cond: () => true },
    { key: "build", nextKey: "sbom", nextLabel: "Generate SBOM", cond: () => true },
    { key: "sbom", nextKey: "activation", nextLabel: "Test Activation", cond: () => true },
    { key: "activation", nextKey: "archive", nextLabel: "Deposit & Share", cond: () => true },
    { key: "archive", nextKey: "seal", nextLabel: "Seal", cond: () => true },
    { key: "seal", nextKey: null, nextLabel: null, cond: () => false },
  ];
  const step = STEPS.find((workflowStep) => workflowStep.key === stepKey);
  if (!step || !step.nextKey || !step.nextLabel) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "9px 14px",
        background: C.accentBg,
        border: `1px solid ${C.accentBorder}`,
        borderRadius: 9,
        marginBottom: 20,
        animation: "fadeUp 0.2s ease",
      }}
    >
      <span style={{ color: C.accent, display: "flex", flexShrink: 0 }}>{Ic.chevR()}</span>
      <span style={{ fontSize: 13, color: C.textMid, fontFamily: F.sans, flex: 1 }}>
        Next step:
      </span>
      <button
        type="button"
        onClick={() => onGo(step.nextKey)}
        style={{
          ...actionBtn({
            border: "none",
            padding: "5px 12px",
            background: C.accent,
            color: "#fff",
          }),
          display: "flex",
          alignItems: "center",
          gap: 5,
          cursor: "pointer",
          flexShrink: 0,
          borderRadius: 6,
          transition: "background 0.13s",
        }}
        {...hoverBg("#1d4ed8", C.accent)}
      >
        {step.nextLabel} →
      </button>
    </div>
  );
}

// Which script fields does each service actually execute?
const SVC_SCRIPT_FIELDS: Record<
  string,
  Array<{ label: string; fieldKey: keyof Ree; scriptKind: "build" | "validate" }>
> = {
  build: [{ label: "Build script", fieldKey: "build_runtime_script", scriptKind: "build" }],
  activation: [
    { label: "Activation script", fieldKey: "activation_script", scriptKind: "validate" },
  ],
};

interface WorkflowPageHeaderProps {
  color: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  tips?: string[];
  runDone?: boolean;
  badge?: ServiceBadge | null;
  ts?: string;
  timestampPrefix?: string;
  missingCount?: number;
  onGoFields?: () => void;
  rightAction?: React.ReactNode;
}

function WorkflowPageHeader({
  color,
  icon,
  title,
  subtitle,
  tips = [],
  runDone,
  badge,
  ts,
  timestampPrefix = "Last run",
  missingCount = 0,
  onGoFields,
  rightAction,
}: WorkflowPageHeaderProps) {
  return (
    <div
      style={{
        flexShrink: 0,
        padding: "16px 28px 14px",
        borderBottom: `1px solid ${C.border}`,
        background: "rgba(255,255,255,0.7)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: `${color}18`,
          color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: C.text, letterSpacing: -0.2 }}>
            {title}
          </span>
          {runDone && badge && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: badge.color,
                background: badge.bg,
                border: `1px solid ${badge.color}40`,
                borderRadius: 99,
                padding: "2px 9px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {Ic.check(10)} {badge.label}
            </span>
          )}
          {missingCount > 0 && onGoFields && (
            <button
              type="button"
              style={{
                ...actionBtn({
                  fontSize: 11,
                  borderRadius: 99,
                  padding: "2px 9px",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#dc2626",
                  transition: "all 0.12s",
                }),
                display: "flex",
                alignItems: "center",
                gap: 4,
                cursor: "pointer",
              }}
              onClick={onGoFields}
            >
              {Ic.info(10)} {missingCount} missing field{missingCount > 1 ? "s" : ""} ← fix
            </button>
          )}
        </div>
        <div style={{ fontSize: 12, color: C.textMuted, marginTop: 1 }}>{subtitle}</div>
        {tips.length > 0 && (
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 3 }}>
            {tips.map((tip) => (
              <div
                key={tip}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 6,
                  fontSize: 11,
                  color: C.textMid,
                  lineHeight: 1.4,
                  fontFamily: F.sans,
                }}
              >
                <span style={{ color, display: "flex", marginTop: 1, flexShrink: 0 }}>
                  {Ic.info(10)}
                </span>
                <span>{tip}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      {rightAction}
      {runDone && ts && (
        <span style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, flexShrink: 0 }}>
          {timestampPrefix}{" "}
          {new Date(ts).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      )}
    </div>
  );
}

interface ServiceActionSectionProps {
  color: string;
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  idleLabel: string;
  runningLabel: string;
  doneLabel?: string;
  helperText: string;
  onRun: () => void;
}

function ServiceActionSection({
  color,
  running,
  runDone,
  disabled,
  idleLabel,
  runningLabel,
  doneLabel = "Re-run",
  helperText,
  onRun,
}: ServiceActionSectionProps) {
  const buttonLabel = running ? runningLabel : runDone ? doneLabel : idleLabel;
  return (
    <div
      style={{ padding: "20px 24px 16px", flexShrink: 0, borderBottom: `1px solid ${C.border}` }}
    >
      <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Action</div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onRun}
          disabled={disabled}
          style={{
            ...actionBtn({
              border: "none",
              borderRadius: 8,
              padding: "8px 18px",
              fontWeight: 700,
            }),
            display: "flex",
            alignItems: "center",
            gap: 7,
            background: disabled ? `${color}22` : color,
            cursor: disabled ? "default" : "pointer",
            color: disabled ? color : "#fff",
          }}
        >
          <span
            style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
          >
            {running ? Ic.loader(14) : Ic.play(14)}
          </span>
          {buttonLabel}
        </button>
        <div style={S_TEXT_MUTED_11}>{helperText}</div>
      </div>
    </div>
  );
}

// ── DependencyPanel ───────────────────────────────────────────────────────────
interface DependencyPanelProps {
  depGroups: DepGroup[];
}
function DependencyPanel({ depGroups }: DependencyPanelProps) {
  const [openGroups, setOpenGroups] = useState(() =>
    Object.fromEntries(depGroups.map((g) => [g.path, true])),
  );
  const [filter, setFilter] = useState("all"); // all | exact | range | none

  const totalPkgs = depGroups.reduce((sum, group) => sum + group.packages.length, 0);
  const pinnedCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "exact").length,
    0,
  );
  const rangeCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "range").length,
    0,
  );
  const noneCount = depGroups.reduce(
    (sum, group) => sum + group.packages.filter((pkg) => pkg.pinned === "none").length,
    0,
  );

  const toggle = (path: string) => setOpenGroups((o) => ({ ...o, [path]: !o[path] }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, minHeight: 0 }}>
      {/* ── Summary row ── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {[
          {
            key: "all",
            label: `${totalPkgs} total`,
            color: C.textMid,
            bg: C.surfaceAlt,
            border: C.border,
          },
          { key: "exact", label: `${pinnedCount} pinned`, ...PIN_META.exact },
          { key: "range", label: `${rangeCount} range`, ...PIN_META.range },
          { key: "none", label: `${noneCount} unpinned`, ...PIN_META.none },
        ].map((summaryFilter) => (
          <button
            type="button"
            key={summaryFilter.key}
            onClick={() => setFilter(summaryFilter.key)}
            style={{
              ...actionBtn({
                fontSize: 11,
                borderRadius: 99,
                padding: "3px 10px",
                transition: "all 0.12s",
              }),
              color: summaryFilter.color,
              background: filter === summaryFilter.key ? summaryFilter.bg : "transparent",
              border: `1.5px solid ${filter === summaryFilter.key ? summaryFilter.border : C.border}`,
              cursor: "pointer",
            }}
            {...hoverIf(filter !== summaryFilter.key, hoverBg(summaryFilter.bg, "transparent"))}
            {...hoverIf(
              filter !== summaryFilter.key,
              hoverBorderColor(summaryFilter.border, C.border),
            )}
          >
            {summaryFilter.label}
          </button>
        ))}
      </div>

      {/* ── File groups ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {depGroups.map((group) => {
          const visiblePkgs =
            filter === "all" ? group.packages : group.packages.filter((p) => p.pinned === filter);
          if (visiblePkgs.length === 0 && filter !== "all") return null;
          const ecoMeta = ECO_META[group.ecosystem] || ECO_META.pip;
          const isOpen = openGroups[group.path] !== false;
          const groupPinned = group.packages.filter((p) => p.pinned === "exact").length;
          const groupUnpinned = group.packages.filter((p) => p.pinned === "none").length;

          return (
            <div
              key={group.path}
              style={{
                border: `1.5px solid ${ecoMeta.color}35`,
                borderRadius: 10,
                overflow: "hidden",
                background: "rgba(255,255,255,0.7)",
              }}
            >
              {/* Group header */}
              <button
                type="button"
                onClick={() => toggle(group.path)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "9px 12px",
                  background: `${ecoMeta.color}12`,
                  borderTopWidth: 0,
                  borderLeftWidth: 0,
                  borderRightWidth: 0,
                  borderBottomWidth: isOpen ? 1 : 0,
                  borderBottomStyle: "solid",
                  borderBottomColor: isOpen ? `${ecoMeta.color}25` : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "background 0.12s",
                }}
                {...hoverBg(`${ecoMeta.color}1e`, `${ecoMeta.color}12`)}
              >
                <span style={{ display: "flex", color: ecoMeta.color }}>{Ic.file(13)}</span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    color: ecoMeta.color,
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {group.path}
                </span>
                {/* eco badge */}
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: ecoMeta.color,
                    background: ecoMeta.bg,
                    border: `1px solid ${ecoMeta.color}40`,
                    borderRadius: 99,
                    padding: "1px 6px",
                    fontFamily: F.sans,
                    flexShrink: 0,
                  }}
                >
                  {ecoMeta.label}
                </span>
                {/* mini stats */}
                <span
                  style={{
                    fontSize: 10,
                    color: "#16a34a",
                    fontFamily: F.mono,
                    flexShrink: 0,
                    marginLeft: 4,
                  }}
                >
                  {groupPinned}✓
                </span>
                {groupUnpinned > 0 && (
                  <span
                    style={{ fontSize: 10, color: "#dc2626", fontFamily: F.mono, flexShrink: 0 }}
                  >
                    {groupUnpinned}✗
                  </span>
                )}
                <span style={{ display: "flex", color: C.textMuted, marginLeft: 4 }}>
                  {isOpen ? Ic.chevD(12) : Ic.chevR(12)}
                </span>
              </button>

              {/* Package rows */}
              {isOpen && (
                <div>
                  {/* Column headers */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 130px 80px",
                      gap: 0,
                      padding: "4px 12px",
                      background: C.surfaceAlt,
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    {["Package", "Version / Constraint", "Status"].map((h) => (
                      <span
                        key={h}
                        style={{
                          ...S_SECTION_LABEL,
                          fontSize: 10,
                          letterSpacing: 0.8,
                        }}
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                  {(filter === "all" ? group.packages : visiblePkgs).map((pkg, i) => {
                    const pm = PIN_META[pkg.pinned] || PIN_META.none;
                    return (
                      <div
                        key={`${pkg.name}:${pkg.version ?? ""}:${pkg.raw}`}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "1fr 130px 80px",
                          gap: 0,
                          padding: "5px 12px",
                          borderBottom: `1px solid ${C.border}`,
                          background: i % 2 === 0 ? "transparent" : "#fafbfd",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 5, minWidth: 0 }}>
                          {pkg.dev && (
                            <span
                              style={{
                                fontSize: 9,
                                color: ECO_META.dev.color,
                                background: ECO_META.dev.bg,
                                border: `1px solid ${ECO_META.dev.color}40`,
                                borderRadius: 3,
                                padding: "0 3px",
                                fontFamily: F.sans,
                                fontWeight: 700,
                                flexShrink: 0,
                              }}
                            >
                              dev
                            </span>
                          )}
                          {pkg.ecosystem === "pip" && (
                            <span
                              style={{
                                fontSize: 9,
                                color: ECO_META.pip.color,
                                background: ECO_META.pip.bg,
                                border: `1px solid ${ECO_META.pip.color}40`,
                                borderRadius: 3,
                                padding: "0 3px",
                                fontFamily: F.sans,
                                fontWeight: 700,
                                flexShrink: 0,
                              }}
                            >
                              pip
                            </span>
                          )}
                          <span
                            style={{
                              fontSize: 12,
                              fontFamily: F.mono,
                              color: C.text,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {pkg.name}
                          </span>
                        </div>
                        <span
                          style={{
                            fontSize: 11,
                            fontFamily: F.mono,
                            color: pkg.version ? C.textMid : C.textMuted,
                            fontStyle: pkg.version ? "normal" : "italic",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            alignSelf: "center",
                          }}
                        >
                          {pkg.version || "—"}
                        </span>
                        <span style={{ alignSelf: "center" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: pm.color,
                              background: pm.bg,
                              border: `1px solid ${pm.border}`,
                              borderRadius: 99,
                              padding: "1px 6px",
                              fontFamily: F.sans,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {pm.label}
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RequirementsBanner({
  status,
  items = [],
  onAction,
  actionLabel,
}: RequirementsBannerProps) {
  const isMissing = status === "missing";

  return (
    <div
      style={{
        background: isMissing ? "#fef2f2" : "#f0fdf4",
        border: `1px solid ${isMissing ? "#fecaca" : "#bbf7d0"}`,
        borderRadius: 10,
        padding: "12px 16px",
        marginBottom: 20,
        display: "flex",
        gap: 12,
        alignItems: "flex-start",
      }}
    >
      <span
        style={{
          color: isMissing ? "#dc2626" : "#16a34a",
          flexShrink: 0,
          marginTop: 1,
          display: "flex",
        }}
      >
        {isMissing ? Ic.info() : Ic.check()}
      </span>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: isMissing ? "#dc2626" : "#16a34a",
            marginBottom: items.length > 0 ? 5 : 0,
          }}
        >
          {isMissing ? "Missing required fields" : "All required fields set"}
        </div>

        {items.length > 0 && (
          <div
            style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: onAction ? 8 : 0 }}
          >
            {items.map((item) => (
              <span
                key={item.field}
                style={{
                  fontSize: 12,
                  fontFamily: F.sans,
                  color: isMissing ? "#dc2626" : "#16a34a",
                  background: isMissing ? "#fff" : "#dcfce7",
                  border: `1px solid ${isMissing ? "#fecaca" : "#bbf7d0"}`,
                  borderRadius: 4,
                  padding: "2px 8px",
                }}
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {onAction && actionLabel && (
          <button
            type="button"
            onClick={onAction}
            style={{
              ...actionBtn({
                border: `1px solid ${C.accentBorder}`,
                borderRadius: 6,
                padding: "4px 10px",
                background: "transparent",
                color: C.accent,
              }),
              cursor: "pointer",
            }}
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// RuntimeOutputNode — shows build output check + "Set as runtime" action
interface RuntimeOutputNodeProps {
  expectedOutput: string;
  buildDone: boolean;
  ree: Ree;
  imageColor: string;
  files: FileTreeNode[];
}
function RuntimeOutputNode({
  expectedOutput,
  buildDone,
  ree,
  imageColor,
  files,
}: RuntimeOutputNodeProps) {
  // Treat expectedOutput always as a file path (tarball or other file).
  const isTarball = expectedOutput && /\.(tar\.gz|tgz)$/i.test(expectedOutput);
  const alreadySet = expectedOutput && ree.runtime === expectedOutput;

  const fileExists = isTarball
    ? !!(function find(nodes) {
        for (const node of nodes || []) {
          if (
            node.type === "file" &&
            (node.name === expectedOutput || expectedOutput.endsWith(`/${node.name}`))
          )
            return node;
          if (node.children) {
            const foundNode = find(node.children);
            if (foundNode) return foundNode;
          }
        }
      })(files || [])
    : false;

  const state = !expectedOutput
    ? "unset"
    : !buildDone
      ? "pending"
      : fileExists
        ? "found"
        : "missing";

  const colors = {
    unset: { border: C.border, bg: C.surfaceAlt, text: C.textMuted, icon: C.textMuted },
    pending: { border: C.accentBorder, bg: C.accentBg, text: C.accent, icon: C.accent },
    found: { border: `${imageColor}60`, bg: "#ecfeff", text: imageColor, icon: imageColor },
    missing: { border: "#fca5a5", bg: "#fef2f2", text: "#dc2626", icon: "#dc2626" },
    // no image-ref state; expectedOutput is always a file path
  };
  const col = colors[state];
  const hasActionRow = state === "missing";

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: col.bg,
          border: `1.5px solid ${col.border}`,
          borderRadius: hasActionRow ? "8px 8px 0 0" : 8,
          transition: "all 0.3s",
          boxShadow: expectedOutput ? `0 0 0 3px ${col.border}30` : "none",
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
            background: `${col.icon}18`,
          }}
        >
          <span style={{ color: col.icon, display: "flex" }}>{Ic.archive(14)}</span>
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              ...S_SECTION_LABEL_SMALL,
              letterSpacing: 0.8,
              color: col.text,
              opacity: 0.7,
              marginBottom: 1,
            }}
          >
            {state === "unset" ? "Build output" : "Runtime file"}
          </div>
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              fontFamily: F.mono,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: col.text,
            }}
          >
            {expectedOutput || (
              <span
                style={{ fontStyle: "italic", fontWeight: 400, fontSize: 11, color: C.textMuted }}
              >
                not specified
              </span>
            )}
          </div>
          {expectedOutput && (
            <div
              style={{
                fontSize: 10,
                color: col.text,
                opacity: 0.7,
                fontFamily: F.sans,
                marginTop: 1,
              }}
            >
              {state === "pending" && "will be checked after build runs"}
              {state === "found" && "✓ produced by build"}
              {state === "missing" && "✗ not found after build"}
            </div>
          )}
        </div>
        {state === "found" && (
          <span
            style={{
              ...S_STATUS_BADGE_SM_BASE,
              color: imageColor,
              background: `${imageColor}18`,
              border: `1px solid ${imageColor}40`,
            }}
          >
            FOUND
          </span>
        )}
        {state === "missing" && (
          <span
            style={{
              ...S_STATUS_BADGE_SM_BASE,
              color: "#dc2626",
              background: "#fef2f2",
              border: "1px solid #fecaca",
            }}
          >
            NOT FOUND
          </span>
        )}
        {alreadySet && (
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

      {/* Manual setting removed: runtime is auto-detected from build output. */}

      {state === "missing" && (
        <div
          style={{
            padding: "9px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderTop: "none",
            borderRadius: "0 0 8px 8px",
          }}
        >
          <span style={{ fontSize: 11, color: "#dc2626", fontFamily: F.sans, lineHeight: 1.4 }}>
            Expected <code style={{ fontFamily: F.mono, fontSize: 10.5 }}>{expectedOutput}</code>{" "}
            but it wasn't produced. Check your build script writes to this path.
          </span>
        </div>
      )}
    </div>
  );
}

const SERVICE_PAGE_COMPONENTS: Record<string, (props: ServicePageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} ui={EXPLORER_SCREENS_UI} />,
  build: (props) => <PageBuildRuntime {...props} ui={EXPLORER_SCREENS_UI} />,
  sbom: (props) => <PageGenerateSBOM {...props} ui={EXPLORER_SCREENS_UI} />,
  activation: (props) => <PageTestActivation {...props} ui={EXPLORER_SCREENS_UI} />,
};

const EXPLORER_SCREENS_UI: ExplorerScreensUi = {
  WorkflowPageHeader,
  FieldSection,
  FieldRow,
  FieldTipsSidebar,
  NextStepNudge,
  SourceUrlField,
  SourceUploadField,
  RequirementsBanner,
  ServiceActionSection,
  LevelBadge,
  DependencyPanel,
  FilePicker,
  RuntimeField,
  RuntimeOutputNode,
  ScriptPanel,
  LogPanel,
  descToTwoTierTips,
  findFileByPath,
  SVC_SCRIPT_FIELDS,
  FIELD_META,
  actionBtn,
  inp,
  hoverBg,
  hoverBorderColor,
  hoverColor,
};

// ══════════════════════════════════════════════════════════════════════════════
// OVERVIEW — pod visualisation page
// ══════════════════════════════════════════════════════════════════════════════

// ── Panel Cable Overlay ────────────────────────────────────────────────────────
// Cables connecting side panels → specimen pod sphere.
// Uses svg.getScreenCTM() to map the sphere's SVG-space centre (290,290) into
// page pixels, so the endpoints stay glued to the actual rendered sphere no
// matter how the layout reflows or the window resizes.
// ── Reusable clickable field row for overview panels ───────────────────────────

// ══════════════════════════════════════════════════════════════════════════════
// NAV COMPONENTS — defined at module scope so React never unmounts them on
// Explorer re-renders (defining components inside render recreates their
// identity every render, forcing React to unmount/remount).
// ══════════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════════
// EXPLORER — shell with left nav
// ══════════════════════════════════════════════════════════════════════════════
interface ExplorerProps {
  onBack: () => void;
}
function Explorer({ onBack }: ExplorerProps) {
  const WORKSPACE_ID = "active";
  const [ree, setRee] = useState<Ree>(DEMO_REE);
  const [locked, setLocked] = useState(false);
  const [repoMode, setRepoMode] = useState("url");
  const [actionStates, setActionStates] = useState<ActionStates>({});
  const [badges, setBadges] = useState<Badges>({});
  const [timestamps, setTimestamps] = useState<Timestamps>({});
  const [serviceLogs, setServiceLogs] = useState<ServiceLogs>({});
  const [serviceParams, setServiceParams] = useState<ServiceParams>(() => initialServiceParams());
  const [toast, setToast] = useState<ToastState | null>(null);
  const [page, setPage] = useState<ExplorerPage>(PAGE.SOURCE); // see PAGE constant for valid values
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [virtualFiles, setVirtualFiles] = useState<FileTreeNode[]>([]);
  const [immutableSourceSnapshotFiles, setImmutableSourceSnapshotFiles] = useState<FileTreeNode[]>(
    [],
  );
  const [immutableSourceSnapshotArchiveName, setImmutableSourceSnapshotArchiveName] = useState("");

  const [showReviewerPreview, setShowReviewerPreview] = useState(false);

  const currentReeArchiveEntries = useMemo(
    () =>
      buildCurrentReeArchiveEntries(
        ree,
        virtualFiles,
        immutableSourceSnapshotFiles,
        immutableSourceSnapshotArchiveName,
      ),
    [ree, virtualFiles, immutableSourceSnapshotFiles, immutableSourceSnapshotArchiveName],
  );
  const currentReeFiles = useMemo(
    () => reeArchiveEntriesToFiles(currentReeArchiveEntries),
    [currentReeArchiveEntries],
  );

  const showToast = (msg: string, type: ToastState["type"] = "info") =>
    setToast({ message: msg, type });
  const level = ree._evalLevel ?? 0; // only set by running Evaluate

  const executeServiceRun = async (
    key: string,
    params: Record<string, unknown> = {},
  ): Promise<WorkspaceServiceLogEntry> => {
    setActionStates((prevStates) => ({ ...prevStates, [key]: "loading" }));
    await new Promise((resolve) => setTimeout(resolve, 1600 + Math.random() * 700));

    const isEvaluateRun = key === PAGE.EVALUATE;
    const newLevel = isEvaluateRun ? computeEvaluateLevelFromFiles(virtualFiles || []) : level;
    const lines = makeLogs(key, ree, params, newLevel);
    const ts = new Date().toISOString();

    setServiceLogs((prevLogs) => ({ ...prevLogs, [key]: { lines, ts } }));
    setActionStates((prevStates) => ({ ...prevStates, [key]: "done" }));
    setBadges((prevBadges) => ({ ...prevBadges, [key]: true }));
    setTimestamps((prevTimestamps) => ({ ...prevTimestamps, [key]: ts }));

    const serviceHandler = SERVICE_RUN_HANDLERS[key];
    if (serviceHandler) {
      serviceHandler(params, newLevel);
      return { lines, ts };
    }

    if (key === "create") {
      setLocked(true);
      showToast("REE created — fields locked", "success");
    } else if (key === "swh") {
      const swhid = `swh:1:dir:${Math.random().toString(16).slice(2, 14)}`;
      setRee((prevRee) => ({ ...prevRee, swhid }));
      showToast("Archived at Software Heritage — SWHID assigned", "success");
    } else if (key === "zenodo") {
      const doi = `10.5281/zenodo.${Math.floor(Math.random() * 9000000 + 1000000)}`;
      setRee((prevRee) => ({ ...prevRee, zenodo_doi: doi }));
      showToast("Published on Zenodo — DOI assigned", "success");
    } else if (key === "dataverse") {
      const doi = `doi:10.5072/DVN/${Math.floor(Math.random() * 900000 + 100000)}`;
      setRee((prevRee) => ({ ...prevRee, dataverse_doi: doi }));
      showToast("Dataset published on Dataverse — DOI assigned", "success");
    } else {
      const svc = SERVICES.find((service) => service.key === key);
      showToast(`${svc?.label ?? key} completed`, "success");
    }

    return { lines, ts };
  };

  const workspaceService: IWorkspaceService<FileTreeNode> = createInMemoryDummyWorkspaceService<
    FileTreeNode,
    Ree["source_type"]
  >({
    getWorkspaceFiles: () => virtualFiles,
    updateWorkspaceFiles: setVirtualFiles,
    upsertFile: (previous, path, content) => upsertWorkspaceFile(previous, path, content),
    runScript: async (scriptKey: string): Promise<WorkspaceServiceLogEntry> => {
      const params = serviceParams[scriptKey] ?? {};
      return executeServiceRun(scriptKey, params);
    },
    clearWorkspace: () => {
      setVirtualFiles([]);
      setImmutableSourceSnapshotFiles([]);
      setImmutableSourceSnapshotArchiveName("");
      setRee((prevRee) => ({
        ...prevRee,
        _sourceAvailable: false,
        _sourceAcquiredBy: undefined,
        _uploadedArchive: "",
        _sourceSnapshotArchive: "",
        _sourceSnapshotCapturedAt: "",
      }));
    },
    loadWorkspaceFromUpload: (archiveName: string) => {
      const ts = new Date().toISOString();
      const workspaceFiles = makeDummyWorkspaceFromArchiveUpload(
        MOCK_FILES,
        archiveName,
        PAGE.SOURCE,
      );
      const snapshotFiles = cloneDummyWorkspaceTree(workspaceFiles);
      const snapshotArchiveName = normalizeSnapshotArchiveName(archiveName);

      setVirtualFiles(workspaceFiles);
      setImmutableSourceSnapshotFiles(snapshotFiles);
      setImmutableSourceSnapshotArchiveName(snapshotArchiveName);
      setRee((prevRee) => ({
        ...prevRee,
        _uploadedArchive: archiveName,
        source_type: "",
        _sourceAvailable: true,
        _sourceAcquiredBy: "upload",
        _sourceSnapshotArchive: snapshotArchiveName,
        _sourceSnapshotCapturedAt: ts,
      }));
    },
    loadWorkspaceFromDownload: (sourceUrl: string, sourceType: Ree["source_type"]) => {
      if (!sourceUrl || !sourceType) return;

      const ts = new Date().toISOString();
      const workspaceFiles = makeDummyWorkspaceFromOrigin(
        MOCK_FILES,
        sourceUrl,
        sourceType,
        PAGE.SOURCE,
      );
      const snapshotFiles = cloneDummyWorkspaceTree(workspaceFiles);
      const repoBase =
        (sourceUrl.split("/").filter(Boolean).pop() || "source").replace(
          /\.(git|tar\.gz|tgz|zip)$/i,
          "",
        ) || "source";
      const snapshotArchiveName = normalizeSnapshotArchiveName(`${repoBase}-original.tar.gz`);

      setVirtualFiles(workspaceFiles);
      setImmutableSourceSnapshotFiles(snapshotFiles);
      setImmutableSourceSnapshotArchiveName(snapshotArchiveName);
      setRee((prevRee) => ({
        ...prevRee,
        origin_url: sourceUrl,
        source_type: sourceType,
        _sourceAvailable: true,
        _sourceAcquiredBy: "download",
        _uploadedArchive: "",
        _sourceSnapshotArchive: snapshotArchiveName,
        _sourceSnapshotCapturedAt: ts,
      }));
    },
    getDefaultSource: () => ree.origin_url,
    getDefaultSourceType: () => ree.source_type || "git",
  });

  const handleSeal = () => {
    const sealHash =
      "sha256:" +
      Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
    setRee((prevRee) => ({
      ...prevRee,
      _sealedAt: new Date().toISOString(),
      _sealHash: sealHash,
    }));
    setLocked(true);
    showToast("REE sealed — now read-only", "success");
  };

  const handleDownloadRee = () => {
    const blob = buildZipBlob(currentReeArchiveEntries);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(ree.name || "ree").replace(/[^a-z0-9_-]/gi, "_")}-capsule.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${ree.name || "ree"}-capsule.zip`, "success");
  };

  // Reset all derived/workflow state when source in workspace changes
  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    setBadges({});
    setTimestamps({});
    setServiceLogs({});
    setActionStates({});
    setServiceParams(initialServiceParams());
    setRee((prevRee) => ({
      ...prevRee,
      build_runtime_script: "",
      activation_script: "",
      sbom: "",
      swhid: "",
      detected_dependencies: "",
      repro_level: "",
      _evalLevel: 0,
      _sourceAvailable: false,
      _sourceAcquiredBy: undefined,
      zenodo_doi: "",
      _uploadedArchive: "",
      _sourceSnapshotArchive: "",
      _sourceSnapshotCapturedAt: "",
    }));
    setVirtualFiles([]);
    setImmutableSourceSnapshotFiles([]);
    setImmutableSourceSnapshotArchiveName("");
    if (!options.silent) {
      showToast("Source changed — workflow status and scripts reset", "info");
    }
  };

  const handleDownloadSourceFiles = async (originType: Ree["source_type"]) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "upload") {
      showToast(
        "Source already provided via tarball upload. Change source to switch method.",
        "error",
      );
      return;
    }
    if (!ree.origin_url || !originType) {
      showToast("Set origin URL and origin type first", "error");
      return;
    }
    handleSourceChange({ silent: true });
    setActionStates((prevStates) => ({ ...prevStates, source: "loading" }));
    await new Promise((resolve) => setTimeout(resolve, 1400));
    setActionStates((prevStates) => ({ ...prevStates, source: "done" }));
    setBadges((prevBadges) => ({ ...prevBadges, source: true }));
    const ts = new Date().toISOString();
    setTimestamps((prevTimestamps) => ({ ...prevTimestamps, source: ts }));
    await workspaceService.resetWorkspace(
      WORKSPACE_ID,
      JSON.stringify({ mode: "download", source: ree.origin_url, sourceType: originType }),
    );
    showToast(
      originType === "tarball"
        ? "Tarball downloaded and extracted into workspace"
        : "Source files downloaded into workspace",
      "success",
    );
  };

  const handleWorkspaceUpload = (payload: SourceUploadCommit) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "download") {
      showToast(
        "Source already provided via origin download. Change source to switch method.",
        "error",
      );
      return;
    }
    handleSourceChange({ silent: true });
    const ts = new Date().toISOString();

    const archiveName = payload.archiveName || "source.tar.gz";
    void workspaceService.resetWorkspace(
      WORKSPACE_ID,
      JSON.stringify({ mode: "upload", archiveName }),
    );
    setBadges((prevBadges) => ({ ...prevBadges, source: true }));
    setTimestamps((prevTimestamps) => ({ ...prevTimestamps, source: ts }));
    showToast("Archive extracted into workspace", "success");
  };

  const handleRemoveWorkspaceSource = () => {
    handleSourceChange({ silent: true });
    void workspaceService.resetWorkspace(WORKSPACE_ID, JSON.stringify({ mode: "clear" }));
    showToast("Source files removed from workspace — choose download or upload again", "info");
  };

  const SERVICE_RUN_HANDLERS: Record<
    string,
    (params: Record<string, unknown>, newLevel: number) => void
  > = {
    build: (serviceParams) => {
      const runtimeTarget = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
      const expectedOutput = String(
        serviceParams?._expectedOutput ? serviceParams._expectedOutput : "",
      ).trim();
      const producedName = expectedOutput || runtimeTarget || "runtime.tar.gz";
      const isTarball = /\.(tar\.gz|tgz)$/i.test(producedName);
      let producedRuntimePath: string | null = null;
      if (isTarball) {
        void workspaceService.updateFile(
          WORKSPACE_ID,
          producedName,
          `[mock binary — docker save | gzip output]\nBuilt: ${new Date().toISOString()}\nSize: ~1.2 GB (mock)`,
        );
        producedRuntimePath = producedName;
      }
      if (expectedOutput && producedRuntimePath && producedRuntimePath === expectedOutput) {
        setRee((prevRee) => ({ ...prevRee, runtime: expectedOutput, _runtimeIncluded: true }));
      } else if (expectedOutput && !producedRuntimePath) {
        showToast(
          `Build finished, but expected runtime file was not produced: ${expectedOutput}`,
          "error",
        );
      }
      showToast(`Build complete${producedName ? ` — ${producedName} produced` : ""}`, "success");
    },
    sbom: () => {
      const sbomContent = JSON.stringify(
        {
          spdxVersion: "SPDX-2.3",
          dataLicense: "CC0-1.0",
          SPDXID: "SPDXRef-DOCUMENT",
          name: `${ree.name || "ree"}-sbom`,
          documentNamespace: `https://example.org/sbom/${ree.name || "ree"}-${Date.now()}`,
          creationInfo: {
            created: new Date().toISOString(),
            creators: ["Tool: syft via REE Explorer"],
          },
          packages: [
            {
              SPDXID: "SPDXRef-numpy",
              name: "numpy",
              versionInfo: "1.26.4",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-pandas",
              name: "pandas",
              versionInfo: "2.2.1",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-scipy",
              name: "scipy",
              versionInfo: "1.12.0",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-biopython",
              name: "biopython",
              versionInfo: "1.83",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
          ],
        },
        null,
        2,
      );
      const fname = "sbom.spdx.json";
      void workspaceService.updateFile(WORKSPACE_ID, fname, sbomContent);
      setRee((prevRee) => ({ ...prevRee, sbom: fname }));
      showToast("SBOM generated — sbom.spdx.json", "success");
    },
    activation: () => {
      showToast("Activation test passed — container started cleanly", "success");
    },
    evaluate: (_, newLevel) => {
      const depSummary = (() => {
        const groups = scanDependencies(virtualFiles || MOCK_FILES);
        const depCount = groups.reduce((sum, group) => sum + group.packages.length, 0);
        const manifestCount = groups.length;
        return `${depCount} dependenc${depCount === 1 ? "y" : "ies"} across ${manifestCount} manifest file${manifestCount === 1 ? "" : "s"}`;
      })();
      setRee((prevRee) => ({
        ...prevRee,
        _evalLevel: newLevel,
        repro_level: `L${newLevel} · ${LEVELS[Math.min(newLevel, 7)].label}`,
        detected_dependencies: depSummary,
      }));
      showToast(`L${newLevel} · ${LEVELS[Math.min(newLevel, 7)].label}`, "success");
    },
  };

  const runAction = async (key: string, params: Record<string, unknown> = {}) => {
    setServiceParams((prev) => ({ ...prev, [key]: { ...(prev[key] ?? {}), ...params } }));
    await executeServiceRun(key, params);
  };

  // ── Workflow steps ─────────────────────────────────────────────────────────────
  const WORKFLOW_STEPS = [
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
      svc: SERVICES.find((service) => service.key === PAGE.EVALUATE),
      desc: "Score reproducibility level",
    },
    {
      n: 4,
      key: PAGE.BUILD,
      label: "Build Runtime",
      IC: Ic.cpu,
      svc: SERVICES.find((service) => service.key === PAGE.BUILD),
      desc: "Build the runtime tarball",
    },
    {
      n: 5,
      key: PAGE.SBOM,
      label: "Generate SBOM",
      IC: Ic.package,
      svc: SERVICES.find((service) => service.key === PAGE.SBOM),
      desc: "Scan runtime with syft",
    },
    {
      n: 6,
      key: PAGE.ACTIVATION,
      label: "Test Activation",
      IC: Ic.shield,
      svc: SERVICES.find((service) => service.key === PAGE.ACTIVATION),
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

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      {/* Top bar */}
      <header
        style={{
          height: 48,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          position: "sticky",
          top: 0,
          zIndex: 100,
          flexShrink: 0,
          boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 5,
            color: C.textMuted,
            padding: "4px 8px",
            borderRadius: 6,
            transition: "all 0.12s",
          }}
          {...hoverColor(C.textMid, C.textMuted)}
          {...hoverBg(C.surfaceAlt, "transparent")}
        >
          {Ic.arrowLeft()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
        </button>
        <div style={{ width: 1, height: 18, background: C.border }} />
        <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          REE Explorer
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
      </header>

      {/* Body: nav + content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        {/* Left nav — collapsible: full labels or icons-only */}
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
          {/* iconBtn: render helper (not a component — holds no state, safe to define inline) */}
          {((): React.ReactNode => {
            const iconBtn = (
              key: string,
              icon: React.ReactNode,
              label: string,
              subtitle?: string | null,
            ) => {
              const isActive = page === key;
              return (
                <NavEntryButton
                  title={navCollapsed ? label : undefined}
                  onClick={() => setPage(key as ExplorerPage)}
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
                    <span style={{ display: "flex", color: isActive ? "#fff" : C.textMuted }}>
                      {icon}
                    </span>
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
              <>
                {/* Top toggle button */}
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
                    onClick={() => setNavCollapsed((c) => !c)}
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

                {/* Overview + Browse Files */}
                <div
                  style={{
                    padding: navCollapsed ? "8px 6px 4px" : "8px 8px 4px",
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  {iconBtn("overview", Ic.layers(12), "Overview", "pod · level · state")}
                </div>
                <div
                  style={{
                    padding: navCollapsed ? "4px 6px 8px" : "4px 8px 8px",
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  {iconBtn("files", Ic.files(12), "Browse Files", null)}
                </div>

                {/* Workflow label */}
                {!navCollapsed && (
                  <div style={{ padding: "10px 14px 4px" }}>
                    <span
                      style={{
                        ...S_SECTION_LABEL,
                        fontSize: 10,
                        letterSpacing: 1.3,
                      }}
                    >
                      Workflow
                    </span>
                  </div>
                )}
                {navCollapsed && <div style={{ height: 8 }} />}

                {/* Numbered steps */}
                <div
                  style={{
                    padding: navCollapsed ? "0 6px" : "0 8px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 1,
                    flex: 1,
                  }}
                >
                  {WORKFLOW_STEPS.map((step, i) => {
                    const isActive = page === step.key;
                    const svc = step.svc;
                    let hasRun = false;
                    if (step.key === PAGE.SOURCE) hasRun = !!ree._sourceAvailable;
                    else if (step.key === PAGE.METADATA) hasRun = !!ree.name;
                    else if (step.key === PAGE.SEAL) hasRun = !!ree._sealedAt;
                    else if (step.key === PAGE.ARCHIVE)
                      hasRun = !!badges?.swh || !!badges?.zenodo || !!badges?.dataverse;
                    else hasRun = !!badges?.[step.key];
                    const running = svc && actionStates[step.key] === "loading";
                    const ts = timestamps[step.key];
                    const tsShort = ts
                      ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                      : null;
                    const isLast = i === WORKFLOW_STEPS.length - 1;

                    return (
                      <div key={step.key} style={{ display: "flex", flexDirection: "column" }}>
                        <NavEntryButton
                          title={
                            navCollapsed
                              ? `${step.n}. ${step.label}${tsShort ? ` — last run ${tsShort}` : ""}`
                              : undefined
                          }
                          onClick={() => setPage(step.key as ExplorerPage)}
                          isActive={isActive}
                          navCollapsed={navCollapsed}
                        >
                          {/* Step bubble */}
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
                              border: isActive
                                ? "none"
                                : `1.5px solid ${hasRun ? C.accentBorder : C.border}`,
                              position: "relative",
                              transition: "all 0.2s",
                            }}
                          >
                            {running ? (
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
                            {hasRun && !running && !isActive && (
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

                          {/* Label — hidden when collapsed */}
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
                                {running ? "running…" : tsShort ? `last run ${tsShort}` : step.desc}
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

                {/* Download and Preview button — pinned to nav bottom */}
                <div
                  style={{
                    marginTop: "auto",
                    padding: navCollapsed ? "8px 6px" : "8px 8px",
                    borderTop: `1px solid ${C.border}`,
                  }}
                >
                  {/* Download button — always available (even if not sealed) */}
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
                      onClick={handleDownloadRee}
                    />
                  </div>
                  {/* Preview button — always available (even if not sealed) */}
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
                    onClick={() => setShowReviewerPreview(true)}
                  />
                </div>
              </>
            );
          })()}
        </nav>

        {/* Main content */}
        <main
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            minWidth: 0,
            position: "relative",
            background:
              "linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 35%, #fff5f9 65%, #f4f8ff 100%)",
          }}
        >
          {/* Gradient blobs that the frosted glass blurs */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              zIndex: 0,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                width: 480,
                height: 320,
                borderRadius: "50%",
                top: -80,
                left: "10%",
                background: "radial-gradient(ellipse, #c7d9ff88 0%, transparent 70%)",
              }}
            />
            <div
              style={{
                position: "absolute",
                width: 360,
                height: 280,
                borderRadius: "50%",
                top: 20,
                right: "5%",
                background: "radial-gradient(ellipse, #e0d0ff66 0%, transparent 70%)",
              }}
            />
            <div
              style={{
                position: "absolute",
                width: 300,
                height: 200,
                borderRadius: "50%",
                top: 160,
                left: "35%",
                background: "radial-gradient(ellipse, #ffd6e855 0%, transparent 70%)",
              }}
            />
          </div>
          <div
            style={{
              position: "relative",
              zIndex: 1,
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              minWidth: 0,
            }}
          >
            {(page === PAGE.OVERVIEW || page === PAGE.SEAL) && (
              <div
                style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}
              >
                <PageOverview
                  ree={ree}
                  onReeChange={setRee}
                  level={level}
                  onNavigate={(key) => setPage(key as ExplorerPage)}
                  badges={badges}
                  timestamps={timestamps}
                  onGoField={(key) => {
                    setPage(FIELD_TO_PAGE[String(key)] || PAGE.METADATA);
                    setFocusedField(key);
                  }}
                  files={virtualFiles}
                  snapshotFiles={immutableSourceSnapshotFiles}
                  locked={locked}
                  onSeal={handleSeal}
                  onPreviewReviewer={() => setShowReviewerPreview(true)}
                  onDownloadRee={ree._sealedAt ? handleDownloadRee : undefined}
                />
              </div>
            )}
            {page === PAGE.SOURCE && (
              <PageSourceRepoEntry
                ree={ree}
                onChange={setRee}
                locked={locked}
                repoMode={repoMode}
                onRepoModeChange={setRepoMode}
                onSourceChange={handleSourceChange}
                badges={badges}
                onDownloadSource={(originType) => handleDownloadSourceFiles(originType)}
                onWorkspaceUpload={handleWorkspaceUpload}
                onRemoveWorkspaceSource={handleRemoveWorkspaceSource}
                downloadRunning={actionStates.source === "loading"}
                downloadDone={!!ree._sourceAvailable}
                onGoService={(key) => setPage(key as ExplorerPage)}
                focusedField={focusedField}
                setFocusedField={setFocusedField}
                ui={EXPLORER_SCREENS_UI}
              />
            )}
            {page === PAGE.METADATA && (
              <PageMetadataEntry
                ree={ree}
                onChange={setRee}
                locked={locked}
                setLocked={setLocked}
                badges={badges}
                onGoService={(key) => setPage(key as ExplorerPage)}
                focusedField={focusedField}
                setFocusedField={setFocusedField}
                ui={EXPLORER_SCREENS_UI}
              />
            )}
            {SERVICES.map((svc) => {
              if (page !== svc.key) return null;
              const ServicePageComponent = SERVICE_PAGE_COMPONENTS[svc.key];
              if (!ServicePageComponent) return null;
              const params = serviceParams[svc.key] ?? defaultParamsForService(svc);
              const setParam = (paramKey: string, value: unknown) => {
                setServiceParams((prev) => ({
                  ...prev,
                  [svc.key]: {
                    ...(prev[svc.key] ?? defaultParamsForService(svc)),
                    [paramKey]: value,
                  },
                }));
              };

              return (
                <div
                  key={svc.key}
                  style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
                >
                  <ServicePageComponent
                    svc={svc}
                    ree={ree}
                    log={serviceLogs[svc.key]}
                    running={actionStates[svc.key] === "loading"}
                    runDone={!!badges[svc.key]}
                    badge={badges[svc.key] ? svc.badge : null}
                    ts={timestamps[svc.key]}
                    onRun={runAction}
                    onGoFields={() => {
                      const sourceFieldKeys: (keyof Ree)[] = [
                        "origin_url",
                        "source_type",
                        "_sourceAvailable",
                      ];
                      const hasSourceGap = missingRequirements(svc, ree).some((req) =>
                        sourceFieldKeys.includes(req.field),
                      );
                      setPage(hasSourceGap ? PAGE.SOURCE : PAGE.METADATA);
                    }}
                    badges={badges}
                    onGo={(key) => setPage(key as ExplorerPage)}
                    files={virtualFiles}
                    onFilesChange={setVirtualFiles}
                    onReeChange={setRee}
                    missing={missingRequirements(svc, ree)}
                    params={params}
                    setParam={setParam}
                    ui={EXPLORER_SCREENS_UI}
                  />
                </div>
              );
            })}
            {page === PAGE.ARCHIVE && (
              <div
                style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
              >
                <ArchivePage
                  ree={ree}
                  badges={badges}
                  logs={serviceLogs}
                  actionStates={actionStates}
                  onRun={runAction}
                  onGo={(key) => setPage(key as ExplorerPage)}
                  WorkflowPageHeaderComponent={WorkflowPageHeader}
                  RequirementsBannerComponent={RequirementsBanner}
                  LogPanelComponent={LogPanel}
                  NextStepNudgeComponent={NextStepNudge}
                />
              </div>
            )}
            {page === PAGE.FILES && (
              <div
                style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
              >
                <FilesPage
                  files={virtualFiles}
                  reeFiles={currentReeFiles}
                  WorkflowPageHeaderComponent={WorkflowPageHeader}
                />
              </div>
            )}
          </div>
        </main>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <ReviewerPreviewOverlay
        open={showReviewerPreview}
        ree={ree}
        onClose={() => setShowReviewerPreview(false)}
        defaultRee={SEALED_DEMO_REE}
        LevelBadge={LevelBadge}
        PodOrbitControl={PodOrbitControl}
        ReviewerViewComponent={ReviewerFeatureView}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// REVIEWER EXPLORER — Read-only verification view
// ══════════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════════
// REVIEWER VIEW
// ══════════════════════════════════════════════════════════════════════════════

// ── Reproducibility level badge ────────────────────────────────────────────────
interface LevelBadgeProps {
  level: number;
  large?: boolean;
}
function LevelBadge({ level, large = false }: LevelBadgeProps) {
  const levelMeta = LEVELS[Math.min(level, 7)];
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: large ? 8 : 5,
        padding: large ? "6px 12px" : "3px 8px",
        background: levelMeta.bg,
        border: `1.5px solid ${levelMeta.color}40`,
        borderRadius: large ? 8 : 5,
      }}
    >
      <div
        style={{
          width: large ? 8 : 6,
          height: large ? 8 : 6,
          borderRadius: "50%",
          background: levelMeta.color,
          boxShadow: `0 0 6px ${levelMeta.color}80`,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          fontSize: large ? 13 : 11,
          fontWeight: 700,
          fontFamily: F.mono,
          color: levelMeta.color,
          letterSpacing: 0.4,
        }}
      >
        L{level} · {levelMeta.label}
      </span>
    </div>
  );
}

// ── Pod Orbit Control — pod + arc progress ring + launch button ────────────────
interface PodOrbitControlProps {
  level: number;
  levelMeta: Level;
  stepStates: Record<string, StepState>;
  allDone: boolean;
  isRunningAll: boolean;
  onRunAll: () => void;
}
function PodOrbitControl({
  level,
  levelMeta,
  stepStates,
  allDone,
  isRunningAll,
  onRunAll,
}: PodOrbitControlProps) {
  const podSize = 300;
  const cx = podSize / 2,
    cy = podSize / 2;
  const ringR = cx - 6;
  const steps = REACTIVATION_STEPS;
  const gapDeg = 7;
  const segDeg = (360 - gapDeg * steps.length) / steps.length;

  const ringPt = (deg, r = ringR) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const arcD = (startDeg, endDeg, r = ringR) => {
    const startPoint = ringPt(startDeg, r),
      endPoint = ringPt(endDeg, r);
    return `M ${startPoint.x} ${startPoint.y} A ${r} ${r} 0 ${endDeg - startDeg > 180 ? 1 : 0} 1 ${endPoint.x} ${endPoint.y}`;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 24 }}>
      <div style={{ position: "relative", width: podSize, height: podSize }}>
        <div
          style={{
            position: "absolute",
            top: -14,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 3,
            whiteSpace: "nowrap",
          }}
        >
          <LevelBadge level={level} large />
        </div>
        <svg
          width={podSize}
          height={podSize}
          style={{ position: "absolute", inset: 0, overflow: "visible", zIndex: 2 }}
        >
          <title>Reactivation steps</title>
          <circle
            cx={cx}
            cy={cy}
            r={ringR}
            fill="none"
            stroke={levelMeta.color}
            strokeWidth="1"
            opacity="0.12"
            strokeDasharray="4 6"
          />
          {steps.map((step, i) => {
            const startDeg = i * (segDeg + gapDeg),
              endDeg = startDeg + segDeg;
            const state = stepStates[step.key];
            const isDone = state === "done",
              isRun = state === "loading";
            const color = isDone ? "#22c55e" : isRun ? step.color : `${levelMeta.color}30`;
            const width = isDone ? 9 : isRun ? 10 : 5;
            const midPt = ringPt(startDeg + segDeg / 2, ringR + 20);
            return (
              <g key={step.key}>
                <path
                  d={arcD(startDeg, endDeg)}
                  stroke={`${levelMeta.color}15`}
                  strokeWidth="10"
                  fill="none"
                  strokeLinecap="round"
                />
                <path
                  d={arcD(startDeg, endDeg)}
                  stroke={color}
                  strokeWidth={width}
                  fill="none"
                  strokeLinecap="round"
                  style={{ transition: "stroke 0.4s, stroke-width 0.25s" }}
                />
                {isDone && (
                  <path
                    d={arcD(startDeg, endDeg)}
                    stroke="#22c55e"
                    strokeWidth="18"
                    fill="none"
                    strokeLinecap="round"
                    opacity="0.1"
                  />
                )}
                <circle
                  cx={midPt.x}
                  cy={midPt.y}
                  r={isDone ? 6 : isRun ? 5 : 4}
                  fill={isDone ? "#22c55e" : isRun ? step.color : `${levelMeta.color}50`}
                  style={{ transition: "all 0.3s" }}
                />
                {isDone && <circle cx={midPt.x} cy={midPt.y} r={2.5} fill="white" />}
              </g>
            );
          })}
        </svg>
        <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
          <PodWidget level={level} size={podSize} />
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
          marginTop: 2,
        }}
      >
        <div
          style={{
            width: 2,
            height: 16,
            background: `linear-gradient(to bottom, ${levelMeta.color}60, ${levelMeta.color}20)`,
            borderRadius: 1,
          }}
        />
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: levelMeta.color,
            opacity: 0.35,
            marginTop: -1,
          }}
        />
      </div>

      <button
        type="button"
        onClick={onRunAll}
        disabled={isRunningAll || allDone}
        onMouseEnter={(mouseEvent) => {
          if (!isRunningAll && !allDone)
            mouseEvent.currentTarget.style.transform = "translateY(-1px) scale(1.01)";
        }}
        onMouseLeave={(mouseEvent) => {
          mouseEvent.currentTarget.style.transform = "none";
        }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 40px",
          borderRadius: 14,
          background: allDone
            ? "linear-gradient(135deg, #f0fdf4, #dcfce7)"
            : isRunningAll
              ? `${levelMeta.color}18`
              : `linear-gradient(135deg, ${levelMeta.color} 0%, ${levelMeta.ink} 100%)`,
          color: allDone ? "#16a34a" : isRunningAll ? levelMeta.color : "#fff",
          border: allDone
            ? "1.5px solid #bbf7d0"
            : isRunningAll
              ? `1.5px solid ${levelMeta.color}35`
              : "none",
          fontSize: 15,
          fontWeight: 700,
          fontFamily: F.sans,
          letterSpacing: 0.2,
          cursor: isRunningAll || allDone ? "default" : "pointer",
          boxShadow:
            !allDone && !isRunningAll
              ? `0 6px 28px ${levelMeta.color}45, 0 2px 10px ${levelMeta.color}30, inset 0 1px 0 rgba(255,255,255,0.22)`
              : allDone
                ? "0 3px 14px #22c55e20"
                : "none",
          transition: "all 0.2s",
        }}
      >
        <span
          style={{
            display: "flex",
            animation: isRunningAll ? "spin 0.9s linear infinite" : "none",
          }}
        >
          {allDone ? Ic.check(18) : isRunningAll ? Ic.loader(18) : Ic.play(18)}
        </span>
        {allDone ? "All stages verified" : isRunningAll ? "Reactivating…" : "Run Full Reactivation"}
      </button>

      <div
        style={{
          display: "flex",
          gap: 6,
          marginTop: 12,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {steps.map((step) => {
          const state = stepStates[step.key];
          const isDone = state === "done",
            isRun = state === "loading";
          return (
            <div
              key={step.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "3px 8px",
                borderRadius: 5,
                background: isDone ? "#f0fdf4" : isRun ? `${step.color}12` : C.surfaceAlt,
                border: `1px solid ${isDone ? "#bbf7d0" : isRun ? `${step.color}40` : C.border}`,
                transition: "all 0.3s",
              }}
            >
              <div
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: isDone ? "#22c55e" : isRun ? step.color : C.borderMid,
                  boxShadow: isRun ? `0 0 6px ${step.color}` : "none",
                  transition: "all 0.3s",
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.sans,
                  fontWeight: isDone || isRun ? 600 : 400,
                  color: isDone ? "#16a34a" : isRun ? step.color : C.textMuted,
                }}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<AppPage>(APP_PAGE.LANDING);
  return (
    <AppProvider>
      <style>{GLOBAL_CSS}</style>
      <AppRoutes
        page={page}
        onGoLanding={() => setPage(APP_PAGE.LANDING)}
        onGoExplorer={() => setPage(APP_PAGE.EXPLORER)}
        onGoReviewer={() => setPage(APP_PAGE.REVIEWER)}
        LandingView={LandingView}
        ExplorerView={Explorer}
        ReviewerView={({ onBack }) => (
          <ReviewerFeatureView
            onBack={onBack}
            defaultRee={SEALED_DEMO_REE}
            LevelBadge={LevelBadge}
            PodOrbitControl={PodOrbitControl}
          />
        )}
      />
    </AppProvider>
  );
}
