import {
  lgColors,
  lgContentCard,
  lgInput,
  lgPrimaryActionButton,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useEffect, useState } from "react";

interface RunScriptCardProps {
  // Workspace-relative path the script is stored at. When set, it is shown as a
  // mono caption under the helper.
  scriptPath?: string;
  currentContent: string;
  // Persist the edited script content to the workspace at scriptPath.
  onSave: (content: string) => void;
  label?: string;
  helper?: string;
  defaultTemplate?: string;
  disabled?: boolean;
  // Optional header icon rendered beside the label.
  icon?: React.ReactNode;
  // Button content and footer status text — overridable so callers (e.g. the
  // reserved build script) can speak in their own terms.
  saveButtonContent?: React.ReactNode;
  savedLabel?: string;
  unsavedLabel?: string;
}

const DEFAULT_TEMPLATE = `#!/usr/bin/env sh
set -eu

# This script fully defines how this runnable executes — it owns entering the
# runtime. For a Docker runtime, for example:
#
# docker run --rm -v "$(pwd):/workspace" -w /workspace my-runtime:latest \\
#   python main.py
`;

// A self-contained editor for a runnable's run script — used by activation, each
// experiment, and (via props) the reserved build script. The script lives in
// the workspace overlay; this card edits and persists it.
export function RunScriptCard({
  scriptPath,
  currentContent,
  onSave,
  label = "Run script",
  helper = "This runnable owns its run script: it fully defines how it executes, including entering the runtime.",
  defaultTemplate = DEFAULT_TEMPLATE,
  disabled = false,
  icon,
  saveButtonContent = "Save run script",
  savedLabel = "Saved run script",
  unsavedLabel = "Unsaved run script",
}: RunScriptCardProps) {
  const [content, setContent] = useState(currentContent || defaultTemplate);
  const [savedContent, setSavedContent] = useState(currentContent);

  // Resets when the persisted content changes (e.g. after a save round-trips).
  // defaultTemplate is a dependency, so callers MUST pass a stable reference (a
  // module-level constant) — an inline-constructed template would re-run this on
  // every render and clobber the user's unsaved edits.
  useEffect(() => {
    setContent(currentContent || defaultTemplate);
    setSavedContent(currentContent);
  }, [currentContent, defaultTemplate]);

  const dirty = content !== savedContent;

  const header = (
    <div>
      <div style={lgStyles.label}>{label}</div>
      <div style={lgStyles.helper}>{helper}</div>
      {scriptPath && (
        <div style={{ marginTop: 4, fontFamily: F.mono, fontSize: 11, color: lgColors.textMuted }}>
          {scriptPath}
        </div>
      )}
    </div>
  );

  return (
    <div style={lgContentCard()}>
      {icon ? (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10 }}>
          <span style={{ color: lgColors.blue }}>{icon}</span>
          {header}
        </div>
      ) : (
        <div style={{ marginBottom: 10 }}>{header}</div>
      )}

      <textarea
        aria-label={label}
        value={content}
        onChange={(event) => setContent(event.target.value)}
        spellCheck={false}
        disabled={disabled}
        rows={13}
        style={textareaStyle}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 10,
          alignItems: "center",
          marginTop: 10,
          flexWrap: "wrap",
        }}
      >
        <span style={{ ...lgStyles.helper, color: dirty ? lgColors.warning : lgColors.textMuted }}>
          {dirty ? unsavedLabel : savedLabel}
        </span>
        <button
          type="button"
          disabled={disabled || !content.trim() || !dirty}
          onClick={() => {
            onSave(content);
            setSavedContent(content);
          }}
          style={lgPrimaryActionButton(disabled || !content.trim() || !dirty)}
        >
          {saveButtonContent}
        </button>
      </div>
    </div>
  );
}

const textareaStyle: React.CSSProperties = {
  ...lgInput(false),
  boxSizing: "border-box",
  width: "100%",
  resize: "vertical",
  minHeight: 240,
  padding: "10px 11px",
  fontSize: 12,
  lineHeight: 1.55,
  fontFamily: F.mono,
};
