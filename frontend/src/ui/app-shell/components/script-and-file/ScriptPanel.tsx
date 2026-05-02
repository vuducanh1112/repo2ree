import { useEffect, useMemo, useState } from "react";
import { PAGE } from "../../../../application/app-shell/AppShellPages";
import type { ReeDraftViewModel } from "../../../../domain/ree/ReeSpec";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import {
  removeWorkspaceFileByPath,
  upsertWorkspaceFileByPath,
} from "../../../../domain/workspace/fileTreeOps";
import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBg, hoverColor, hoverIf } from "../../../theme/theme";
import { defaultScriptTemplates, findFileByPath } from "../../pages/sharedWorkflowHelpers";
import { CodeLineList, getFileTypeStyle, ScriptViewMessage } from "./shared";

interface ScriptPanelProps {
  scriptKind: "build" | "validate" | null;
  fieldKey: keyof ReeDraftViewModel;
  files: FileTreeNode[];
  onFilesChange?: (files: FileTreeNode[]) => void;
  onPersistWorkspaceFile?: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  ree: ReeDraftViewModel;
  onReeChange?: (ree: ReeDraftViewModel) => void;
  onTemplateSuggestedOutput?: (output: string) => void;
  reviewerMode?: boolean;
  saveToWorkspaceOnly?: boolean;
}

type ScriptPanelMode = "view" | "write";

function tabIcon(isActive: boolean, accent: string, icon: JSX.Element) {
  return <span style={{ display: "flex", color: isActive ? accent : C.textMuted }}>{icon}</span>;
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
    if (!templates.some((template) => template.key === templateKey)) {
      setTemplateKey(templates[0].key);
    }
  }, [templateKey, templates]);

  const handleModeChange = (nextMode: ScriptPanelMode) => {
    if (nextMode === "write") {
      const file = scriptPath ? findFileByPath(files, scriptPath) : null;
      setEditorContent(file?.content || editorContent);
      setEditorFilename(scriptPath || editorFilename);
    }
    setMode(nextMode);
    setCollapsed(false);
  };

  const commitFile = async (filename: string, content: string) => {
    const previousPath = scriptPath || undefined;
    const withoutPrevious =
      previousPath && previousPath !== filename
        ? removeWorkspaceFileByPath(files, previousPath)
        : files;
    const updated = upsertWorkspaceFileByPath(withoutPrevious, filename, content, {
      tag: PAGE.SOURCE,
    });
    onFilesChange?.(updated);
    onReeChange?.({ ...ree, [fieldKey]: filename });
    await onPersistWorkspaceFile?.(previousPath, filename, content);
  };

  const handleSave = () => {
    const filename =
      editorFilename.trim() ||
      (scriptKind === "validate" ? "activation_test.sh" : "build_runtime.sh");
    void commitFile(filename, editorContent);
    setMode("view");
  };

  const handleUseTemplate = () => {
    const selected = templates.find((template) => template.key === templateKey);
    if (!selected) return;
    setEditorFilename(scriptPath || selected.filename);
    setEditorContent(selected.content);
    if (scriptKind === "build" && selected.suggestedOutput) {
      onTemplateSuggestedOutput?.(selected.suggestedOutput);
    }
  };

  const typeStyle = getFileTypeStyle(scriptPath || editorFilename);
  const viewLines = existingFile ? (existingFile.content || "").split("\n") : null;
  const tabs: Array<{ key: ScriptPanelMode; label: string; icon: () => JSX.Element }> = [
    ...(hasScript ? [{ key: "view" as const, label: scriptPath, icon: () => Ic.file(12) }] : []),
    ...(!reviewerMode && scriptKind
      ? [
          {
            key: "write" as const,
            label: hasScript ? "Edit" : "Write",
            icon: () => Ic.terminal(12),
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
          display: "flex",
          alignItems: "center",
          background: C.surfaceAlt,
          borderBottom: collapsed && mode === "view" ? "none" : `1px solid ${C.border}`,
        }}
      >
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {tabs.map((tab) => {
            const isActive = mode === tab.key;
            const accent = tabAccent[tab.key];
            return (
              <button
                type="button"
                key={tab.key}
                onClick={() => handleModeChange(tab.key)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 14px",
                  border: "none",
                  cursor: "pointer",
                  transition: "background 0.13s",
                  flexShrink: 0,
                  background: isActive ? tabBg[tab.key] : "transparent",
                  borderRight: `1px solid ${C.border}`,
                  borderBottom: isActive ? `2px solid ${accent}` : "2px solid transparent",
                }}
                {...hoverIf(!isActive, hoverBg(`${C.border}40`, "transparent"))}
              >
                {tabIcon(isActive, accent, tab.icon())}
                <span
                  style={{
                    fontSize: 12,
                    whiteSpace: "nowrap",
                    fontFamily: tab.key === "view" ? F.mono : F.sans,
                    color: isActive ? accent : C.textMid,
                    fontWeight: isActive ? 600 : 400,
                  }}
                >
                  {tab.label}
                </span>
                {tab.key === "view" && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      fontFamily: F.mono,
                      letterSpacing: 0.6,
                      textTransform: "uppercase",
                      padding: "1px 4px",
                      borderRadius: 3,
                      marginLeft: 2,
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
            onClick={() => setCollapsed((value) => !value)}
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
            <div style={{ background: C.surfaceAlt }}>
              {viewLines === null ? (
                <ScriptViewMessage color="#f97316">
                  File not found in repository tree — check the path in metadata fields.
                </ScriptViewMessage>
              ) : viewLines.length === 0 ? (
                <ScriptViewMessage color={C.textMuted} fontStyle="italic">
                  (empty file)
                </ScriptViewMessage>
              ) : (
                <div style={{ padding: "8px 0 10px" }}>
                  <CodeLineList lines={viewLines} />
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
                <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
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
                      {templates.map((template) => (
                        <option key={template.key} value={template.key}>
                          {template.label}
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

                <button
                  type="button"
                  onClick={handleSave}
                  disabled={!editorContent.trim()}
                  style={{
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
                    cursor: !editorContent.trim() ? "default" : "pointer",
                    opacity: !editorContent.trim() ? 0.4 : 1,
                  }}
                  {...hoverIf(!!editorContent.trim(), hoverBg("#dbeafe", C.accentBg))}
                >
                  {Ic.check(11)} Save to workspace
                </button>
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
