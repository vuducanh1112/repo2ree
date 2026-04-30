import { useEffect, useMemo, useRef, useState } from "react";
import { PAGE } from "../../../application/workspace-editor/WorkspaceEditorPages";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import {
  removeWorkspaceFileByPath,
  upsertWorkspaceFileByPath,
} from "../../../domain/workspace/fileTreeOps";
import { Ic, Svg } from "../../shared/components/Icon";
import { fileType } from "../../shared/formatting";
import { C, F, hoverBg, hoverColor, hoverIf, S_SCRIPT_VIEW_MESSAGE_BASE } from "../../theme/theme";
import {
  allFilePaths,
  defaultScriptTemplates,
  findFileByPath,
} from "../pages/sharedWorkflowHelpers";

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

const PREVIEW_LINES = 6;

interface ScriptPanelProps {
  scriptKind: "build" | "validate" | null;
  fieldKey: keyof Ree;
  files: FileTreeNode[];
  onFilesChange?: (files: FileTreeNode[]) => void;
  onPersistWorkspaceFile?: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  ree: Ree;
  onReeChange?: (ree: Ree) => void;
  onTemplateSuggestedOutput?: (output: string) => void;
  reviewerMode?: boolean;
  saveToWorkspaceOnly?: boolean;
}
export function ScriptPanel({
  scriptKind,
  fieldKey,
  files,
  onFilesChange,
  onPersistWorkspaceFile,
  ree,
  onReeChange,
  onTemplateSuggestedOutput,
  reviewerMode,
  saveToWorkspaceOnly = false,
}: ScriptPanelProps) {
  const scriptPath = (ree[fieldKey] as string) || "";
  const existingFile = scriptPath ? findFileByPath(files, scriptPath) : null;
  const hasScript = !!existingFile;

  const originUrl = ree.origin_url || "";
  const isGitHub = /github\.com/i.test(originUrl);
  const isGitLab = /gitlab\.com|gitlab\./i.test(originUrl);
  const isRemoteGit = (isGitHub || isGitLab) && !saveToWorkspaceOnly;

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

  const commitFile = async (fname: string, content: string) => {
    const previousPath = scriptPath || undefined;
    const withoutPrevious =
      previousPath && previousPath !== fname
        ? removeWorkspaceFileByPath(files, previousPath)
        : files;
    const updated = upsertWorkspaceFileByPath(withoutPrevious, fname, content, {
      tag: PAGE.SOURCE,
    });
    onFilesChange?.(updated);
    onReeChange?.({ ...ree, [fieldKey]: fname });
    await onPersistWorkspaceFile?.(previousPath, fname, content);
  };

  const handleSave = () => {
    const fname =
      editorFilename.trim() ||
      (scriptKind === "validate" ? "activation_test.sh" : "build_runtime.sh");
    void commitFile(fname, editorContent);
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

  const Tabs: Array<{ key: ScriptPanelMode; label: string; icon: (s?: number) => JSX.Element }> = [
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
          {Tabs.map((t) => {
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

      {!(collapsed && mode === "view") && (
        <>
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

          {mode === "write" && (
            <div>
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

interface FilePickerProps {
  value: string;
  onChange: (value: string) => void;
  files: FileTreeNode[];
  placeholder?: string;
  disabled?: boolean;
  onFocus?: () => void;
  filterFn?: (path: string) => boolean;
}
export function FilePicker({
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
  const [draft, setDraft] = useState(value || "");

  const prevValue = useRef(value);
  if (prevValue.current !== value) {
    const old = prevValue.current;
    prevValue.current = value;
    setDraft((d) => (d === old ? value || "" : d));
  }

  const allPaths = allFilePaths(files);
  const paths = filterFn ? allPaths.filter(filterFn) : allPaths;

  const trimmedDraft = draft.trim();
  const matchedFile = trimmedDraft ? findFileByPath(files, trimmedDraft) : null;
  const notFound = trimmedDraft.length > 0 && !matchedFile;
  const wrongFormat = filterFn && trimmedDraft.length > 0 && !filterFn(trimmedDraft);
  const ftype = fileType(trimmedDraft);
  const typeStyle = FILE_TYPE_COLORS[ftype] || FILE_TYPE_COLORS.text;

  const previewLines = matchedFile
    ? (matchedFile.content || "").split("\n").slice(0, PREVIEW_LINES)
    : [];
  const hasMore = matchedFile
    ? (matchedFile.content || "").split("\n").length > PREVIEW_LINES
    : false;

  const isValid = matchedFile && !wrongFormat;
  const borderColor = notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.border;

  const handleDraftChange = (raw: string) => {
    setDraft(raw);
    setPreviewOpen(false);
    const trimmed = raw.trim();
    if (!trimmed) {
      onChange("");
      return;
    }
    const file = trimmed ? findFileByPath(files, trimmed) : null;
    const passesFormat = !filterFn || filterFn(trimmed);
    onChange(file && passesFormat ? trimmed : "");
  };

  const handleSelect = (p: string) => {
    setDraft(p);
    setOpen(false);
    setPreviewOpen(true);
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
