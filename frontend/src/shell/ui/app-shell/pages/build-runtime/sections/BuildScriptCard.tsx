import type { RuntimeEntry } from "@core/ree/ReeSpec";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { FilePicker } from "@shell/ui/app-shell/components/scriptAndFile";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgContentCard,
  lgInput,
  lgPrimaryActionButton,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useState } from "react";
import { findFileByPath } from "../../sharedAssemblyHelpers";
import { filterBuildTemplates } from "./buildScriptTemplates";
import { BaseChip, ClearScriptButton, ScriptOriginChip } from "./buildScriptUiPrimitives";

interface BuildScriptCardProps {
  scriptPath: string;
  scriptContent: string;
  runtimeEntry?: RuntimeEntry | null;
  files: FileTreeNode[];
  onSaveFile: (previousPath: string | undefined, path: string, content: string) => void;
  onSelectScript: (path: string) => void;
  onClearScript: () => void;
}

function substrateKey(entry?: RuntimeEntry | null): string {
  if (!entry) return "any";
  return entry.kind === "container" ? `container:${entry.engine}` : entry.kind;
}

export function BuildScriptCard(props: BuildScriptCardProps) {
  const { scriptPath, files } = props;
  const hasScript = !!scriptPath;
  const selectedFile = scriptPath ? findFileByPath(files, scriptPath) : null;
  const selectedIsOverlay = selectedFile?.tag === "generated";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <CreateSection key={substrateKey(props.runtimeEntry)} {...props} />

      {hasScript && <EditSection key={scriptPath} {...props} />}

      <PickSection
        scriptPath={scriptPath}
        hasScript={hasScript}
        selectedIsOverlay={selectedIsOverlay}
        files={files}
        onSelectScript={props.onSelectScript}
        onClearScript={props.onClearScript}
      />
    </div>
  );
}

// ─── Shared script editor primitives ─────────────────────────────────────────

const scriptTextareaStyle: React.CSSProperties = {
  ...lgInput(false),
  fontFamily: F.mono,
  fontSize: 12,
  minHeight: 260,
  resize: "vertical",
  lineHeight: 1.5,
} as React.CSSProperties;

const saveRowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 10,
  marginTop: 10,
  flexWrap: "wrap",
};

// ─── Create section ───────────────────────────────────────────────────────────
// Fresh editor, pre-seeded from the substrate template. Saving writes to the
// overlay — does NOT automatically select the file as the active build script.

function CreateSection({ runtimeEntry, onSaveFile }: BuildScriptCardProps) {
  const templates = filterBuildTemplates(runtimeEntry);
  const primary = templates[0];

  const [editorPath, setEditorPath] = useState(primary?.filename || "build_runtime.sh");
  const [editorContent, setEditorContent] = useState(primary?.content || "");
  const [activeTemplate, setActiveTemplate] = useState(primary?.key ?? "");

  const dirty = !!editorContent.trim();

  const seedFrom = (key: string) => {
    const template = templates.find((t) => t.key === key);
    if (!template) return;
    setActiveTemplate(template.key);
    setEditorContent(template.content);
    setEditorPath(template.filename);
  };

  const handleSave = () => {
    const filename = editorPath.trim() || "build_runtime.sh";
    onSaveFile(undefined, filename, editorContent);
  };

  return (
    <div>
      <div style={{ ...lgStyles.label, marginBottom: 8 }}>
        Create new script{" "}
        <span style={{ color: lgColors.textMuted, fontWeight: 400 }}>(optional)</span>
      </div>
      <div style={lgContentCard(0)}>
        {templates.length > 1 && (
          <>
            <div style={{ ...lgStyles.label, marginBottom: 6 }}>Template</div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: 8,
                marginBottom: 14,
              }}
            >
              {templates.map((template) => (
                <BaseChip
                  key={template.key}
                  active={activeTemplate === template.key}
                  label={template.label}
                  hint={template.hint}
                  onClick={() => seedFrom(template.key)}
                />
              ))}
            </div>
          </>
        )}

        <input
          value={editorPath}
          onChange={(e) => setEditorPath(e.target.value)}
          placeholder="build_runtime.sh"
          style={{ ...lgInput(false), minHeight: 38, marginBottom: 10 }}
        />
        <textarea
          value={editorContent}
          onChange={(e) => setEditorContent(e.target.value)}
          spellCheck={false}
          style={scriptTextareaStyle}
        />
        <div style={saveRowStyle}>
          <span style={lgStyles.helper}>
            Saves to the overlay layer — then pick it below to use as the build script.
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={!dirty}
            style={lgPrimaryActionButton(!dirty)}
          >
            {Ic.check(13)} Save to overlay
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Edit section ─────────────────────────────────────────────────────────────
// Edits the content of the currently selected script. The filename is shown as
// a label — renaming is not offered here because it would silently disconnect
// the selection.

function EditSection({ scriptPath, scriptContent, onSaveFile }: BuildScriptCardProps) {
  const [editorContent, setEditorContent] = useState(scriptContent);
  const dirty = editorContent !== scriptContent;

  const handleSave = () => {
    onSaveFile(undefined, scriptPath, editorContent);
  };

  return (
    <div>
      <div style={{ ...lgStyles.label, marginBottom: 8 }}>Edit selected script</div>
      <div style={lgContentCard(0)}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 10,
            padding: "7px 10px",
            borderRadius: 7,
            background: "rgba(241, 245, 249, 0.8)",
            border: "1px solid rgba(148, 163, 184, 0.3)",
          }}
        >
          <span style={{ color: lgColors.textMuted, display: "flex" }}>{Ic.file(13)}</span>
          <span style={{ fontSize: 12, fontFamily: F.mono, color: lgColors.textMid }}>
            {scriptPath}
          </span>
        </div>
        <textarea
          value={editorContent}
          onChange={(e) => setEditorContent(e.target.value)}
          spellCheck={false}
          style={scriptTextareaStyle}
        />
        <div style={saveRowStyle}>
          <span
            style={{
              ...lgStyles.helper,
              color: dirty ? lgColors.warning : lgColors.textMuted,
            }}
          >
            {dirty ? "Unsaved changes" : "In sync with overlay"}
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={!dirty}
            style={lgPrimaryActionButton(!dirty)}
          >
            {Ic.check(13)} Save changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Pick section ─────────────────────────────────────────────────────────────
// The only way to set the active build script. Always visible.

function PickSection({
  scriptPath,
  hasScript,
  selectedIsOverlay,
  files,
  onSelectScript,
  onClearScript,
}: {
  scriptPath: string;
  hasScript: boolean;
  selectedIsOverlay: boolean;
  files: FileTreeNode[];
  onSelectScript: (path: string) => void;
  onClearScript: () => void;
}) {
  const handle = (next: string) => {
    if (!next) {
      onClearScript();
      return;
    }
    onSelectScript(next);
  };

  return (
    <div>
      <div style={{ ...lgStyles.label, marginBottom: 8 }}>Active build script</div>
      <div style={lgContentCard(0)}>
        <FilePicker
          value={scriptPath}
          onChange={handle}
          files={files}
          placeholder="Pick a .sh file from the workspace…"
          filterFn={(path) => /\.sh$/i.test(path)}
        />

        {hasScript && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginTop: 12,
              flexWrap: "wrap",
            }}
          >
            <span style={{ color: lgColors.primaryDeep, display: "flex" }}>{Ic.check(14)}</span>
            <span
              style={{
                fontSize: 12,
                fontFamily: F.mono,
                color: lgColors.primaryDeep,
                fontWeight: 600,
                flex: 1,
                minWidth: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {scriptPath}
            </span>
            <ScriptOriginChip overlay={selectedIsOverlay} />
            <ClearScriptButton onClear={onClearScript} />
          </div>
        )}

        {!hasScript && (
          <div style={{ ...lgStyles.helper, marginTop: 8 }}>
            Pick any <code>.sh</code> in the workspace as the build script.
          </div>
        )}
      </div>
    </div>
  );
}
