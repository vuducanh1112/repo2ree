import { render } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { userEvent } from "vitest/browser";
import "../../theme/index.css";
import { CodeEditor, type CodeEditorMark } from "./CodeEditor";

function Harness({ initial = "", marks }: { initial?: string; marks?: CodeEditorMark[] }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <CodeEditor ariaLabel="Run script" value={value} onChange={setValue} marks={marks} />
      <output>{value}</output>
    </>
  );
}

function themeColor(name: string): string {
  const probe = document.createElement("span");
  probe.style.color = `var(${name})`;
  document.body.appendChild(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
}

describe("CodeEditor in a browser", () => {
  it("uses the browser's real document geometry", async () => {
    const { container } = render(<Harness initial="echo hi" />);
    const line = container.querySelector(".cm-line");
    expect(line).not.toBeNull();

    const range = document.createRange();
    range.selectNodeContents(line as Element);
    await expect.poll(() => range.getBoundingClientRect().width).toBeGreaterThan(0);
  });

  it("reports what was typed as the new script", async () => {
    const { getByLabelText, getByRole } = render(<Harness />);

    await userEvent.click(getByLabelText("Run script"));
    await userEvent.keyboard("echo hi");

    await expect.poll(() => getByRole("status").textContent).toBe("echo hi");
  });

  it("colours shell syntax from the theme rather than CodeMirror's defaults", async () => {
    const { getByLabelText, container } = render(<Harness />);

    await userEvent.click(getByLabelText("Run script"));
    await userEvent.keyboard("# note");

    await expect
      .poll(() => {
        const token = container.querySelector(".cm-line span");
        return token ? getComputedStyle(token).color : "";
      })
      .toBe(themeColor("--code-comment"));
  });

  it("rings the frame when the editor inside it takes focus", async () => {
    const { getByLabelText, container } = render(<Harness />);
    const frame = container.firstElementChild as HTMLElement;

    expect(getComputedStyle(frame).borderTopColor).toBe("rgba(148, 163, 184, 0.35)");

    await userEvent.click(getByLabelText("Run script"));
    await expect
      .poll(() => getComputedStyle(frame).borderTopColor)
      .toBe("rgba(14, 165, 233, 0.58)");
  });

  it("underlines a marked line in the tone its severity carries", async () => {
    const { container } = render(
      <Harness
        initial={"one\ntwo\nthree"}
        marks={[{ line: 2, severity: "error", message: "boom" }]}
      />,
    );

    const range = container.querySelector(".cm-lintRange-error");
    expect(range).not.toBeNull();
    expect(getComputedStyle(range as Element).textDecorationColor).toBe(
      themeColor("--tone-danger-line"),
    );
    expect(container.querySelector(".cm-lint-marker-error")).not.toBeNull();
  });
});
