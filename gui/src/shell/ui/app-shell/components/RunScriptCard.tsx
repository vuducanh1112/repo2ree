import { lineOffset } from "@shell/data/scriptLint/findings";
import type { ScriptTemplateEntry } from "@shell/data/scriptTemplates/catalog";
import { Button } from "@shell/ui/shared/components/Button";
import { Textarea } from "@shell/ui/shared/components/FormControl";
import { Surface } from "@shell/ui/shared/components/Surface";
import { useEffect, useRef, useState } from "react";
import styles from "./RunScriptCard.module.css";

export interface RunScriptCardProps {
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
  templates?: ScriptTemplateEntry[];
  disabled?: boolean;
  // Load content into the editor from outside (e.g. a generated candidate),
  // exactly like a template click: it replaces the editor body locally and
  // leaves it dirty — nothing is persisted until the save button. The `nonce`
  // makes re-loading the same body reapply; bump it on every load.
  externalEdit?: { content: string; nonce: number };
  // Optional header icon rendered beside the label.
  icon?: React.ReactNode;
  // Optional control rendered above the editor (e.g. a "Generate from
  // repository" affordance that loads a candidate via `externalEdit`).
  generateSlot?: React.ReactNode;
  renderAnalysis?: (
    content: string,
    dirty: boolean,
    focusLine: (line: number) => void,
  ) => React.ReactNode;
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
  externalEdit,
  icon,
  generateSlot,
  renderAnalysis,
  saveButtonContent = "Save run script",
  savedLabel = "Saved run script",
  unsavedLabel = "Unsaved run script",
}: RunScriptCardProps) {
  const defaultTemplate = templates?.find((template) => template.is_default)?.body ?? "";
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

  // Apply an external load (a generated candidate) once per nonce, the same way
  // a template click replaces the editor body. Distinct from the sync effect
  // above, which only follows persisted content and never clobbers divergence.
  const appliedNonceRef = useRef<number | null>(null);
  useEffect(() => {
    if (externalEdit && externalEdit.nonce !== appliedNonceRef.current) {
      appliedNonceRef.current = externalEdit.nonce;
      setContent(externalEdit.content);
    }
  }, [externalEdit]);

  const dirty = content !== savedContent;

  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const focusLine = (line: number) => {
    const editor = editorRef.current;
    if (!editor) return;
    const offset = lineOffset(content, line);
    editor.focus();
    editor.setSelectionRange(offset, offset);
  };

  const header = (
    <div>
      <div className={styles.label}>{label}</div>
      <div className={styles.helper}>{helper}</div>
      {scriptPath && <div className={styles.path}>{scriptPath}</div>}
    </div>
  );

  return (
    <Surface>
      {icon ? (
        <div className={styles.headerRow}>
          <span aria-hidden className={styles.headerIcon}>
            {icon}
          </span>
          {header}
        </div>
      ) : (
        <div className={styles.headerBlock}>{header}</div>
      )}

      {!disabled && templates && templates.length > 0 && (
        <div className={styles.templates}>
          <span className={styles.templatesLabel}>Templates:</span>
          {templates.map((template) => (
            <Button
              key={template.key}
              size="tiny"
              title={`${template.description} Inserting replaces the editor content; nothing is saved until you save the script.`}
              onClick={() => setContent(template.body)}
            >
              {template.label}
            </Button>
          ))}
        </div>
      )}

      {!disabled && generateSlot}

      <Textarea
        textareaRef={editorRef}
        flavor="code"
        aria-label={label}
        value={content}
        onChange={(event) => setContent(event.target.value)}
        spellCheck={false}
        disabled={disabled}
        rows={13}
      />
      {renderAnalysis?.(content, dirty, focusLine)}

      <div className={styles.footer}>
        <span className={styles.state} data-dirty={dirty || undefined}>
          {dirty ? unsavedLabel : savedLabel}
        </span>
        <div className={styles.actions}>
          {dirty && !disabled && (
            <Button
              size="small"
              title="Discard the unsaved edits and restore the saved script (or the starter template if none is saved yet)."
              onClick={() => setContent(savedContent || defaultTemplate)}
            >
              Discard changes
            </Button>
          )}
          <Button
            variant="primary"
            disabled={disabled || !content.trim() || !dirty}
            onClick={() => {
              onSave(content);
              setSavedContent(content);
            }}
          >
            {saveButtonContent}
          </Button>
        </div>
      </div>
    </Surface>
  );
}
