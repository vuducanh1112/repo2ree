import {
  type BuildScriptMode,
  type BuildScriptSource,
  modeForSource,
  sourceAfterGenerate,
  sourceAfterSave,
} from "@core/ree-assembly/buildRuntimeUiState";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { FilePicker } from "@shell/ui/app-shell/components/scriptAndFile";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgColors,
  lgContentCard,
  lgInfoBanner,
  lgInput,
  lgPrimaryActionButton,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useEffect, useState } from "react";
import { defaultScriptTemplates, findFileByPath } from "../../sharedAssemblyHelpers";
import { BASE_HINTS } from "./buildScriptBaseHints";
import { BaseChip, ModeSegmentedControl, ProvenanceChip } from "./buildScriptUiPrimitives";

interface BuildScriptCardProps {
  scriptPath: string;
  scriptContent: string;
  source: BuildScriptSource | null;
  runtimeHint: string;
  files: FileTreeNode[];
  onCommit: (path: string, content: string) => void;
  onClear: () => void;
  onSourceChange: (source: BuildScriptSource | null) => void;
}

export function BuildScriptCard(props: BuildScriptCardProps) {
  const { scriptPath, source } = props;
  const [mode, setMode] = useState<BuildScriptMode>(modeForSource(source));

  useEffect(() => {
    if (!scriptPath) setMode("pick");
  }, [scriptPath]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <ModeSegmentedControl mode={mode} onChange={setMode} />
        <ProvenanceChip source={scriptPath ? source : null} />
      </div>

      {mode === "pick" && <PickPane {...props} />}
      {mode === "write" && <WritePane key={scriptPath || "__empty"} {...props} />}
      {mode === "generate" && <GeneratePane {...props} />}

      <ScriptStatusBanner
        scriptPath={scriptPath}
        onClear={() => {
          props.onClear();
          props.onSourceChange(null);
        }}
      />
    </div>
  );
}

function PickPane({ scriptPath, files, onCommit, onClear, onSourceChange }: BuildScriptCardProps) {
  const handle = (next: string) => {
    if (!next) {
      onClear();
      onSourceChange(null);
      return;
    }
    const file = findFileByPath(files, next);
    onCommit(next, file?.content || "");
    onSourceChange({ kind: "picked" });
  };
  return (
    <div style={lgContentCard(0)}>
      <div style={{ ...lgStyles.label, marginBottom: 8 }}>Existing build script</div>
      <FilePicker
        value={scriptPath}
        onChange={handle}
        files={files}
        placeholder="build_runtime.sh"
        filterFn={(path) => /\.sh$/i.test(path)}
      />
      <div style={{ ...lgStyles.helper, marginTop: 8 }}>
        Choose any <code>.sh</code> already in the workspace. Picking a different file replaces the
        current selection.
      </div>
    </div>
  );
}

function WritePane({
  scriptPath,
  scriptContent,
  source,
  runtimeHint,
  onCommit,
  onSourceChange,
}: BuildScriptCardProps) {
  const templates = defaultScriptTemplates("build", runtimeHint);
  const [editorPath, setEditorPath] = useState(scriptPath || "build_runtime.sh");
  const [editorContent, setEditorContent] = useState(scriptContent);
  const [seedKey, setSeedKey] = useState("");

  const dirty = editorContent !== scriptContent || editorPath !== scriptPath;
  const hasScript = !!scriptPath;

  const handleSave = () => {
    const filename = editorPath.trim() || "build_runtime.sh";
    onCommit(filename, editorContent);
    onSourceChange(sourceAfterSave(source));
  };

  const handleSeed = () => {
    const template = templates.find((t) => t.key === seedKey);
    if (!template) return;
    setEditorContent(template.content);
    if (!scriptPath) setEditorPath(template.filename);
  };

  return (
    <div style={lgContentCard(0)}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 10,
          marginBottom: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={lgStyles.label}>Script editor</div>
        {source?.kind === "generated" && (
          <span style={lgStyles.helper}>
            Saving will fork this script — it stays based on <strong>{source.base}</strong> but
            loses regenerate-in-place.
          </span>
        )}
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <input
          value={editorPath}
          onChange={(event) => setEditorPath(event.target.value)}
          placeholder="build_runtime.sh"
          style={{ ...lgInput(false), flex: "1 1 200px", minHeight: 38 }}
        />
        <select
          value={seedKey}
          onChange={(event) => setSeedKey(event.target.value)}
          style={{ ...lgInput(false), flex: "1 1 200px", minHeight: 38 }}
        >
          <option value="">Seed from template…</option>
          {templates.map((template) => (
            <option key={template.key} value={template.key}>
              {template.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleSeed}
          disabled={!seedKey}
          style={{
            ...lgInput(!seedKey),
            width: "auto",
            padding: "0 14px",
            minHeight: 38,
            cursor: !seedKey ? "not-allowed" : "pointer",
            fontWeight: 700,
            color: !seedKey ? lgColors.textMuted : lgColors.primaryDeep,
          }}
        >
          Seed
        </button>
      </div>
      <textarea
        value={editorContent}
        onChange={(event) => setEditorContent(event.target.value)}
        spellCheck={false}
        style={{
          ...lgInput(false),
          fontFamily: F.mono,
          fontSize: 12,
          minHeight: 260,
          resize: "vertical",
          lineHeight: 1.5,
        }}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 10,
          marginTop: 10,
          flexWrap: "wrap",
        }}
      >
        <span style={lgStyles.helper}>
          {dirty ? "Unsaved changes" : hasScript ? "In sync with workspace" : "Not saved yet"}
        </span>
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty}
          style={lgPrimaryActionButton(!dirty)}
        >
          {Ic.check(13)} Save to workspace
        </button>
      </div>
    </div>
  );
}

function GeneratePane({ source, runtimeHint, onCommit, onSourceChange }: BuildScriptCardProps) {
  const templates = defaultScriptTemplates("build", runtimeHint);
  const initialBase =
    source?.base && templates.some((t) => t.key === source.base)
      ? source.base
      : templates[0]?.key || "";
  const [generateBase, setGenerateBase] = useState<string>(initialBase);

  const handleGenerate = () => {
    const template = templates.find((t) => t.key === generateBase);
    if (!template) return;
    onCommit(template.filename, template.content);
    onSourceChange(sourceAfterGenerate(template.key));
  };

  return (
    <div style={lgContentCard(0)}>
      <div style={{ ...lgStyles.label, marginBottom: 6 }}>Choose a base</div>
      <div style={{ ...lgStyles.helper, marginBottom: 12 }}>
        Pick the runtime style — the generator will scaffold a build script you can run as-is or
        tweak in <strong>Write</strong>.
      </div>
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
            active={generateBase === template.key}
            label={template.label}
            hint={BASE_HINTS[template.key]}
            onClick={() => setGenerateBase(template.key)}
          />
        ))}
      </div>

      {source?.kind === "generated" && source.edited && (
        <div style={{ ...lgInfoBanner("danger"), marginBottom: 12 }}>
          <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
          <span style={{ fontSize: 12, color: lgColors.danger, fontFamily: F.sans }}>
            The current script was edited after generation. Regenerating will overwrite those edits.
          </span>
        </div>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <span style={lgStyles.helper}>
          Output: <code>{templates.find((t) => t.key === generateBase)?.filename ?? "—"}</code>
        </span>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={!generateBase}
          style={lgPrimaryActionButton(!generateBase)}
        >
          {Ic.layers(13)} {source?.kind === "generated" ? "Regenerate script" : "Generate script"}
        </button>
      </div>
    </div>
  );
}

function ScriptStatusBanner({ scriptPath, onClear }: { scriptPath: string; onClear: () => void }) {
  const hasScript = !!scriptPath;
  return (
    <div
      style={{
        ...lgInfoBanner(hasScript ? "success" : "muted"),
        justifyContent: "space-between",
      }}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontSize: 12,
          color: hasScript ? lgColors.success : lgColors.textMuted,
          fontFamily: F.sans,
          fontWeight: 700,
        }}
      >
        {hasScript ? Ic.check(13) : Ic.info(13)}
        {hasScript ? (
          <>
            Build script: <code>{scriptPath}</code>
          </>
        ) : (
          "No build script selected yet."
        )}
      </span>
      {hasScript && (
        <button
          type="button"
          onClick={onClear}
          style={{
            border: `1px solid ${lgColors.dangerBorder}`,
            background: "rgba(255, 241, 242, 0.82)",
            color: lgColors.danger,
            padding: "5px 10px",
            borderRadius: 6,
            fontWeight: 700,
            fontSize: 11,
            cursor: "pointer",
            fontFamily: F.sans,
          }}
        >
          {Ic.x(11)} Clear
        </button>
      )}
    </div>
  );
}
