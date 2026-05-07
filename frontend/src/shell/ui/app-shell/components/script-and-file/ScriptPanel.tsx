import { useEffect, useMemo, useState } from "react";
import type { ReeSpec } from "../../../../../core/ree/ReeSpec";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import {
  removeWorkspaceFileByPath,
  upsertWorkspaceFileByPath,
} from "../../../../../core/workspace/fileTreeOps";
import { Ic } from "../../../shared/components/Icon";
import { C } from "../../../theme/theme";
import { defaultScriptTemplates, findFileByPath } from "../../pages/sharedAssemblyHelpers";
import { PAGE } from "../../state/pages";
import { type ScriptPanelMode, ScriptPanelTabs, ScriptPanelView } from "./ScriptPanelSections";
import { ScriptPanelWrite } from "./ScriptPanelWriteSection";

interface ScriptPanelProps {
  scriptKind: "build" | "validate" | null;
  fieldKey: keyof ReeSpec;
  files: FileTreeNode[];
  onPersistWorkspaceFile?: (
    previousPath: string | undefined,
    path: string,
    content: string,
  ) => Promise<void>;
  ree: ReeEditorViewModel;
  onReeSpecChange?: React.Dispatch<React.SetStateAction<ReeSpec>>;
  reviewerMode?: boolean;
  saveToWorkspaceOnly?: boolean;
}

export function ScriptPanel({
  scriptKind,
  fieldKey,
  files,
  onPersistWorkspaceFile,
  ree,
  onReeSpecChange,
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
    upsertWorkspaceFileByPath(withoutPrevious, filename, content, {
      tag: PAGE.SOURCE,
    });
    onReeSpecChange?.((current) => ({ ...current, [fieldKey]: filename }));
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
  };

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
      <ScriptPanelTabs
        tabs={tabs}
        mode={mode}
        collapsed={collapsed}
        scriptPath={scriptPath || editorFilename}
        onModeChange={handleModeChange}
        onToggleCollapsed={() => setCollapsed((value) => !value)}
      />

      {!(collapsed && mode === "view") && (
        <>
          {mode === "view" && <ScriptPanelView viewLines={viewLines} />}
          {mode === "write" && (
            <ScriptPanelWrite
              editorFilename={editorFilename}
              editorContent={editorContent}
              templates={templates}
              templateKey={templateKey}
              isRemoteGit={isRemoteGit}
              isGitHub={isGitHub}
              setEditorFilename={setEditorFilename}
              setEditorContent={setEditorContent}
              setTemplateKey={setTemplateKey}
              onUseTemplate={handleUseTemplate}
              onSave={handleSave}
            />
          )}
        </>
      )}
    </div>
  );
}
