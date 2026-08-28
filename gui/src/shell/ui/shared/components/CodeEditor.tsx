import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from "@codemirror/language";
import { shell } from "@codemirror/legacy-modes/mode/shell";
import { type Diagnostic, lintGutter, setDiagnostics } from "@codemirror/lint";
import { Compartment, EditorState, type Text } from "@codemirror/state";
import {
  drawSelection,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { type Ref, useEffect, useImperativeHandle, useRef } from "react";
import styles from "./CodeEditor.module.css";

/** One positioned remark to underline in the document.
 *
 * Deliberately not the API's `Finding`: the editor knows about lines and
 * severities, not about lint tiers or blocking policy. */
export interface CodeEditorMark {
  line: number | null | undefined;
  column?: number | null;
  severity: "error" | "warning" | "info";
  message: string;
  /** The rule that produced the mark, shown in the hover panel. */
  source?: string;
}

/** The imperative surface: the panel below the editor asks to be taken to a line. */
export interface CodeEditorHandle {
  focusLine: (line: number) => void;
}

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  /** Labels the contenteditable, which CodeMirror gives `role="textbox"`. */
  ariaLabel: string;
  disabled?: boolean;
  marks?: readonly CodeEditorMark[];
  handleRef?: Ref<CodeEditorHandle>;
}

/* Colors are custom properties rather than values: the theme layer owns the
 * palette, and a CodeMirror theme is just CSS in an object. */
const highlightStyle = HighlightStyle.define([
  { tag: tags.comment, color: "var(--code-comment)", fontStyle: "italic" },
  { tag: [tags.keyword, tags.controlKeyword, tags.moduleKeyword], color: "var(--code-keyword)" },
  { tag: [tags.string, tags.special(tags.string)], color: "var(--code-string)" },
  { tag: [tags.number, tags.bool], color: "var(--code-number)" },
  {
    tag: [tags.variableName, tags.definition(tags.variableName), tags.propertyName],
    color: "var(--code-variable)",
  },
  { tag: [tags.atom, tags.standard(tags.variableName), tags.meta], color: "var(--code-builtin)" },
  { tag: [tags.operator, tags.punctuation, tags.bracket], color: "var(--code-operator)" },
]);

const editorTheme = EditorView.theme({
  "&": {
    height: "100%",
    color: "var(--ink-default)",
    backgroundColor: "transparent",
    fontSize: "var(--text-label)",
  },
  // The container owns the focus ring, so that a focused editor is skinned
  // exactly like a focused input rather than by CodeMirror's own outline.
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": {
    fontFamily: "var(--font-mono)",
    lineHeight: "var(--leading-normal)",
    overflow: "auto",
  },
  ".cm-content": { padding: "var(--space-2-5) 0", caretColor: "var(--ink-default)" },
  ".cm-line": { padding: "0 var(--space-3)" },
  ".cm-gutters": {
    backgroundColor: "transparent",
    border: "none",
    color: "var(--ink-subtle)",
    paddingLeft: "var(--space-1)",
  },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 var(--space-2) 0 var(--space-3)" },
  ".cm-activeLine": { backgroundColor: "var(--surface-hover)" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--ink-default)" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
    backgroundColor: "var(--surface-selected)",
  },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--ink-default)" },
  // CodeMirror draws its squiggle as a background image with a baked-in color.
  // A wavy underline says the same thing in a color the theme owns.
  ".cm-lintRange": { backgroundImage: "none" },
  ".cm-lintRange-error": { textDecoration: "underline wavy var(--tone-danger-line)" },
  ".cm-lintRange-warning": { textDecoration: "underline wavy var(--tone-warning-line)" },
  ".cm-lintRange-info": { textDecoration: "underline wavy var(--tone-info-line)" },
  ".cm-lint-marker": {
    content: "none",
    width: "var(--space-1-5)",
    height: "var(--space-1-5)",
    margin: "auto",
    borderRadius: "var(--radius-round)",
  },
  ".cm-lint-marker-error": { backgroundColor: "var(--tone-danger-line)" },
  ".cm-lint-marker-warning": { backgroundColor: "var(--tone-warning-line)" },
  ".cm-lint-marker-info": { backgroundColor: "var(--tone-info-line)" },
  ".cm-tooltip": {
    backgroundColor: "var(--surface-overlay)",
    border: "1px solid var(--border-default)",
    borderRadius: "var(--radius-sm)",
    color: "var(--ink-default)",
    fontFamily: "var(--font-sans)",
  },
  ".cm-diagnostic": { borderLeft: "none", padding: "var(--space-1) var(--space-2)" },
});

/** Turn a one-based line/column mark into a document range.
 *
 * Marks arrive from an analysis of source that may already have moved on, so
 * every coordinate is clamped rather than trusted. A mark without a column
 * covers its whole line, which is what a whole-script rule means. */
function markRange(doc: Text, mark: CodeEditorMark): { from: number; to: number } | null {
  if (!mark.line || mark.line < 1 || mark.line > doc.lines) return null;
  const line = doc.line(mark.line);
  const column = mark.column && mark.column > 0 ? mark.column - 1 : 0;
  const from = Math.min(line.from + column, line.to);
  // An empty range renders nothing, so a mark at end of line covers the line.
  return from === line.to && line.from < line.to
    ? { from: line.from, to: line.to }
    : {
        from,
        to: line.to,
      };
}

function diagnostics(doc: Text, marks: readonly CodeEditorMark[]): Diagnostic[] {
  return marks.flatMap((mark) => {
    const range = markRange(doc, mark);
    if (!range) return [];
    return [{ ...range, severity: mark.severity, message: mark.message, source: mark.source }];
  });
}

const NO_MARKS: readonly CodeEditorMark[] = [];

/** A CodeMirror 6 editor skinned as one of the form controls.
 *
 * The view is uncontrolled — CodeMirror owns the document and this component
 * pushes the `value` prop in only when the two have actually diverged, so that
 * a re-render never disturbs the selection of someone mid-edit. */
export function CodeEditor({
  value,
  onChange,
  ariaLabel,
  disabled = false,
  marks = NO_MARKS,
  handleRef,
}: CodeEditorProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<EditorView | null>(null);
  // Read through refs so that a new callback or label never rebuilds the view.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const editableRef = useRef(new Compartment());
  const labelRef = useRef(new Compartment());

  // biome-ignore lint/correctness/useExhaustiveDependencies: value seeds the document once; later changes arrive through the sync effect below
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const view = new EditorView({
      parent: host,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(),
          highlightActiveLine(),
          highlightActiveLineGutter(),
          drawSelection(),
          history(),
          lintGutter(),
          keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
          StreamLanguage.define(shell),
          syntaxHighlighting(highlightStyle),
          EditorState.tabSize.of(2),
          EditorView.lineWrapping,
          editorTheme,
          editableRef.current.of([]),
          labelRef.current.of([]),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChangeRef.current(update.state.doc.toString());
          }),
        ],
      }),
    });
    viewRef.current = view;
    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, []);

  useEffect(() => {
    const view = viewRef.current;
    if (!view || view.state.doc.toString() === value) return;
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } });
  }, [value]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      effects: editableRef.current.reconfigure([
        EditorState.readOnly.of(disabled),
        EditorView.editable.of(!disabled),
      ]),
    });
  }, [disabled]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      effects: labelRef.current.reconfigure(
        EditorView.contentAttributes.of({ "aria-label": ariaLabel }),
      ),
    });
  }, [ariaLabel]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch(setDiagnostics(view.state, diagnostics(view.state.doc, marks)));
  }, [marks]);

  useImperativeHandle(
    handleRef,
    () => ({
      focusLine: (line: number) => {
        const view = viewRef.current;
        if (!view) return;
        const target = view.state.doc.line(Math.min(Math.max(line, 1), view.state.doc.lines));
        view.dispatch({
          selection: { anchor: target.from, head: target.to },
          effects: EditorView.scrollIntoView(target.from, { y: "center" }),
        });
        view.focus();
      },
    }),
    [],
  );

  return <div className={styles.editor} data-disabled={disabled || undefined} ref={hostRef} />;
}
