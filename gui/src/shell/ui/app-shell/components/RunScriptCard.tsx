import type { LintFinding } from "@shell/data/scriptLint/findings";
import type { ScriptTemplateEntry } from "@shell/data/scriptTemplates/catalog";
import { Button } from "@shell/ui/shared/components/Button";
import {
  CodeEditor,
  type CodeEditorHandle,
  type CodeEditorMark,
} from "@shell/ui/shared/components/CodeEditor";
import { Surface } from "@shell/ui/shared/components/Surface";
import { useEffect, useMemo, useRef, useState } from "react";
import styles from "./RunScriptCard.module.css";
import { ScriptDiagnosticsBridge } from "./scriptDiagnostics";

const NO_FINDINGS: readonly LintFinding[] = [];

export interface RunScriptCardProps {
  scriptPath?: string;
  currentContent: string;
  onSave: (content: string) => void;
  label?: string;
  helper?: string;
  templates?: ScriptTemplateEntry[];
  disabled?: boolean;
  externalEdit?: { content: string; nonce: number };
  icon?: React.ReactNode;
  generateSlot?: React.ReactNode;
  renderAnalysis?: (
    content: string,
    dirty: boolean,
    focusLine: (line: number) => void,
  ) => React.ReactNode;
  saveButtonContent?: React.ReactNode;
  savedLabel?: string;
  unsavedLabel?: string;
}

export function RunScriptCard({
  scriptPath,
  currentContent,
  onSave,
  label = "Run script",
  helper = "This runnable owns its run script: it fully defines how it executes, including entering the experiment environment.",
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
  const syncedRef = useRef(currentContent || defaultTemplate);

  useEffect(() => {
    const next = currentContent || defaultTemplate;
    setContent((prev) => (prev === syncedRef.current ? next : prev));
    syncedRef.current = next;
    setSavedContent(currentContent);
  }, [currentContent, defaultTemplate]);

  const appliedNonceRef = useRef<number | null>(null);
  useEffect(() => {
    if (externalEdit && externalEdit.nonce !== appliedNonceRef.current) {
      appliedNonceRef.current = externalEdit.nonce;
      setContent(externalEdit.content);
    }
  }, [externalEdit]);

  const dirty = content !== savedContent;

  const editorRef = useRef<CodeEditorHandle | null>(null);
  const focusLine = (line: number) => editorRef.current?.focusLine(line);

  const [findings, setFindings] = useState<readonly LintFinding[]>(NO_FINDINGS);
  const marks = useMemo<CodeEditorMark[]>(
    () =>
      findings.map((finding) => ({
        line: finding.line,
        column: finding.column,
        severity: finding.severity,
        message: finding.message,
        source: finding.code,
      })),
    [findings],
  );

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

      <CodeEditor
        handleRef={editorRef}
        ariaLabel={label}
        value={content}
        onChange={setContent}
        disabled={disabled}
        marks={marks}
      />
      <ScriptDiagnosticsBridge publish={setFindings}>
        {renderAnalysis?.(content, dirty, focusLine)}
      </ScriptDiagnosticsBridge>

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
