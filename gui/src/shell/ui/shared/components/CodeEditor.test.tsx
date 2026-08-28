import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { CodeEditor, type CodeEditorHandle, type CodeEditorMark } from "./CodeEditor";

// CodeMirror owns a contenteditable, so keystrokes belong to the Chromium
// project (CodeEditor.browser.test.tsx). What is assertable here is everything
// the component drives through props: the document it shows, the label it
// exposes, and the marks it turns into ranges.

function mark(overrides: Partial<CodeEditorMark> = {}): CodeEditorMark {
  return { line: 2, severity: "error", message: "boom", ...overrides };
}

describe("CodeEditor", () => {
  it("labels the editable region so it is reachable by its label", () => {
    render(<CodeEditor ariaLabel="Build script" value={"echo hi\n"} onChange={vi.fn()} />);

    const editor = screen.getByLabelText("Build script");
    expect(editor).toHaveAttribute("contenteditable", "true");
    expect(editor).toHaveTextContent("echo hi");
  });

  it("shows a new document without waiting for a keystroke", () => {
    const { rerender } = render(
      <CodeEditor ariaLabel="Run script" value="first" onChange={vi.fn()} />,
    );
    rerender(<CodeEditor ariaLabel="Run script" value="second" onChange={vi.fn()} />);

    expect(screen.getByLabelText("Run script")).toHaveTextContent("second");
  });

  it("stops being editable while disabled", () => {
    render(<CodeEditor ariaLabel="Run script" value="echo hi" onChange={vi.fn()} disabled />);

    expect(screen.getByLabelText("Run script")).toHaveAttribute("contenteditable", "false");
  });

  it("marks the lines the analysis named", () => {
    render(
      <CodeEditor
        ariaLabel="Run script"
        value={"one\ntwo\nthree"}
        onChange={vi.fn()}
        marks={[mark({ line: 2 })]}
      />,
    );

    expect(document.querySelectorAll(".cm-lintRange-error")).toHaveLength(1);
  });

  it("ignores a mark for a line the document does not have", () => {
    // The analysis runs against source that may already have moved on, so an
    // out-of-range line is an ordinary event, not a crash.
    render(
      <CodeEditor
        ariaLabel="Run script"
        value={"one\n"}
        onChange={vi.fn()}
        marks={[mark({ line: 99 }), mark({ line: null })]}
      />,
    );

    expect(document.querySelectorAll(".cm-lintRange")).toHaveLength(0);
  });

  it("selects the whole line it is sent to", () => {
    const handle = createRef<CodeEditorHandle>();
    render(
      <CodeEditor
        ariaLabel="Run script"
        value={"one\ntwo\nthree"}
        onChange={vi.fn()}
        handleRef={handle}
      />,
    );

    handle.current?.focusLine(2);

    const selection = window.getSelection();
    expect(selection?.toString()).toBe("two");
  });

  it("clamps a line beyond the end rather than throwing", () => {
    const handle = createRef<CodeEditorHandle>();
    render(
      <CodeEditor
        ariaLabel="Run script"
        value={"one\ntwo"}
        onChange={vi.fn()}
        handleRef={handle}
      />,
    );

    expect(() => handle.current?.focusLine(99)).not.toThrow();
  });
});
