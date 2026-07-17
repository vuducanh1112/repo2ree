import type { ScriptTemplateEntryDto } from "@shell/data/scriptTemplates/catalog";
import {
  lgColors,
  lgContentCard,
  lgGlassButton,
  lgInput,
  lgPrimaryActionButton,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useEffect, useRef, useState } from "react";

interface RunScriptCardProps {
  // Workspace-relative path the script is stored at. When set, it is shown as a
  // mono caption under the helper.
  scriptPath?: string;
  currentContent: string;
  // Persist the edited script content to the workspace at scriptPath.
  onSave: (content: string) => void;
  label?: string;
  helper?: string;
  // The catalog section this script prefills from. Renders a picker above the
  // editor; choosing a template replaces the editor content locally — nothing
  // is persisted until the save button. The entry marked `isDefault` doubles
  // as the prefill for a script that doesn't exist yet.
  templates?: ScriptTemplateEntryDto[];
  disabled?: boolean;
  // Optional header icon rendered beside the label.
  icon?: React.ReactNode;
  // Button content and footer status text — overridable so callers (e.g. the
  // reserved build script) can speak in their own terms.
  saveButtonContent?: React.ReactNode;
  savedLabel?: string;
  unsavedLabel?: string;
}

// A self-contained editor for a runnable's run script — used by activation, each
// experiment, and (via props) the reserved build script. The script lives in
// the workspace overlay; this card edits and persists it. Starter templates are
// backend-owned (GET /script-templates): seeded scripts arrive prefilled as file
// content, and scripts that don't exist yet prefill from the entry of
// `templates` the backend marks as the default.
export function RunScriptCard({
  scriptPath,
  currentContent,
  onSave,
  label = "Run script",
  helper = "This runnable owns its run script: it fully defines how it executes, including entering the runtime.",
  templates,
  disabled = false,
  icon,
  saveButtonContent = "Save run script",
  savedLabel = "Saved run script",
  unsavedLabel = "Unsaved run script",
}: RunScriptCardProps) {
  const defaultTemplate = templates?.find((template) => template.isDefault)?.body ?? "";
  const [content, setContent] = useState(currentContent || defaultTemplate);
  const [savedContent, setSavedContent] = useState(currentContent);
  // What the editor was last synced to — the baseline for "has the user
  // diverged". Distinct from savedContent, which tracks persistence for the
  // dirty flag.
  const syncedRef = useRef(currentContent || defaultTemplate);

  // Syncs when the persisted content changes (e.g. after a save round-trips,
  // or when the seeded script / starter template arrives from a background
  // fetch) — but never over the user's unsaved edits: content the user has
  // diverged from the last synced baseline stays put.
  useEffect(() => {
    const next = currentContent || defaultTemplate;
    setContent((prev) => (prev === syncedRef.current ? next : prev));
    syncedRef.current = next;
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

      {!disabled && templates && templates.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: lgColors.textMuted,
              alignSelf: "center",
            }}
          >
            Templates:
          </span>
          {templates.map((template) => (
            <button
              key={template.key}
              type="button"
              title={`${template.description} Inserting replaces the editor content; nothing is saved until you save the script.`}
              onClick={() => setContent(template.body)}
              style={{
                ...lgGlassButton(),
                padding: "3px 9px",
                fontSize: 11,
                fontWeight: 700,
              }}
            >
              {template.label}
            </button>
          ))}
        </div>
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
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {dirty && !disabled && (
            <button
              type="button"
              title="Discard the unsaved edits and restore the saved script (or the starter template if none is saved yet)."
              onClick={() => setContent(savedContent || defaultTemplate)}
              style={{ ...lgGlassButton(), padding: "6px 12px", fontSize: 12 }}
            >
              Discard changes
            </button>
          )}
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
