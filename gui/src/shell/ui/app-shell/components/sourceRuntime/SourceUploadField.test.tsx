import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SourceUploadField } from "./SourceUploadField";

describe("SourceUploadField", () => {
  it("stages, confirms, and cancels a single source archive", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    const { container } = render(<SourceUploadField locked={false} onCommit={onCommit} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const archive = new File(["source"], "source.tar.gz", { type: "application/gzip" });

    await user.upload(input, archive);
    expect(screen.getByText("source.tar.gz")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Discard pending upload" }));
    expect(screen.queryByText("source.tar.gz")).not.toBeInTheDocument();

    await user.upload(input, archive);
    await user.click(screen.getByRole("button", { name: "Add to workspace" }));
    expect(onCommit).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: "archive",
        archiveName: "source.tar.gz",
        archiveFile: archive,
      }),
    );
  });

  it("rejects invalid drops and explains disabled uploads", () => {
    const { rerender } = render(<SourceUploadField locked={false} onCommit={vi.fn()} />);
    const dropzone = screen.getByRole("button", { name: /Drop archive/ });
    fireEvent.dragOver(dropzone);
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [new File(["x"], "notes.txt", { type: "text/plain" })] },
    });
    expect(screen.getByText(/Only a single tarball/)).toBeInTheDocument();

    rerender(
      <SourceUploadField
        locked
        disabledReason="Unlock source configuration first"
        committedName="source.zip"
        onCommit={vi.fn()}
      />,
    );
    expect(screen.getByText("Unlock source configuration first")).toBeInTheDocument();
    expect(screen.getByText("source.zip")).toBeInTheDocument();
  });
});
