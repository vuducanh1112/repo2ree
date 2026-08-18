import { FILE_VIEWER_MAX_CHARS, FILE_VIEWER_MAX_LINES } from "@core/workspace/reeFileTree";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FileViewer } from "./FileViewer";

describe("FileViewer", () => {
  it.each([
    ["Dockerfile", "FROM base", "keyword"],
    ["build.dockerfile", "RUN build", "keyword"],
    ["run.sh", "echo hello", "command"],
    ["run.bash", "# comment", "comment"],
    ["data.json", '  "key": "value"', null],
    ["config.sh", '  "key": "value"', "string"],
    ["notes.txt", "ordinary", null],
  ])("classifies preview syntax for %s", (name, content, syntax) => {
    render(<FileViewer file={{ id: name, name, type: "file", content }} />);
    const code = screen.getByText(content.trim() || " ");
    if (syntax) expect(code).toHaveAttribute("data-syntax", syntax);
    else expect(code).not.toHaveAttribute("data-syntax");
  });

  it("describes binary files whose content is unavailable", () => {
    render(<FileViewer file={{ id: "archive", name: "archive.tar", type: "file", size: 2048 }} />);
    expect(screen.getByText("Binary file (2.0 KB)")).toHaveAttribute("data-muted", "true");
    expect(screen.getByText(/Content preview is unavailable/)).toBeInTheDocument();
  });

  it("describes text files omitted from the API response", () => {
    render(<FileViewer file={{ id: "large", name: "large.txt", type: "file", size: 2048 }} />);
    expect(screen.getByText(/was not inlined/)).toHaveAttribute("data-muted", "true");
    expect(screen.getByText(/Open\/download raw content/)).toBeInTheDocument();
  });

  it("truncates previews by character count", () => {
    render(
      <FileViewer
        file={{
          id: "long",
          name: "long.txt",
          type: "file",
          content: "x".repeat(FILE_VIEWER_MAX_CHARS + 1),
        }}
      />,
    );
    expect(screen.getByText(/Preview truncated/)).toBeInTheDocument();
  });

  it("truncates previews by line count and preserves blank lines", () => {
    const content = Array.from({ length: FILE_VIEWER_MAX_LINES + 1 }, (_, index) =>
      index === 1 ? "" : `line-${index}`,
    ).join("\n");
    render(<FileViewer file={{ id: "lines", name: "lines.txt", type: "file", content }} />);
    expect(screen.getByText(/Preview truncated/)).toBeInTheDocument();
    expect(screen.queryByText(`line-${FILE_VIEWER_MAX_LINES}`)).not.toBeInTheDocument();
  });

  it("renders an empty file as a single blank line", () => {
    const { container } = render(
      <FileViewer file={{ id: "empty", name: "empty.txt", type: "file" }} />,
    );
    expect(container.querySelectorAll("[class*=lineNumber]")).toHaveLength(1);
  });
});
