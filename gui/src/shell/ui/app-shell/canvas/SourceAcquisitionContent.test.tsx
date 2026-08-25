import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { exampleEditorRee } from "../../../../../tests/support/stepPageFixture";
import { SourceAcquisitionContent } from "./SourceAcquisitionContent";

function props(overrides: Record<string, unknown> = {}) {
  const commands = {
    setFocusedField: vi.fn(),
    setRepoMode: vi.fn(),
    onDownloadSourceFiles: vi.fn(),
    onCancelAction: vi.fn(),
    onWorkspaceUpload: vi.fn(),
    onRemoveWorkspaceSource: vi.fn(),
  };
  return {
    ree: { ...exampleEditorRee, originUrl: "", sourceType: "", resolvedRevision: "" },
    workspaceRemote: {
      workspaceSourceState: { sourceAvailable: false, sourceIncluded: false },
      sourceRepo: undefined,
    },
    stepRuns: {
      actionStates: { source: "idle" },
      activeRunIds: { source: undefined },
      timestamps: { source: undefined },
    },
    uiChrome: { focusedField: null, locked: false, repoMode: "url" },
    commands,
    ...overrides,
  } as unknown as ComponentProps<typeof SourceAcquisitionContent>;
}

describe("SourceAcquisitionContent", () => {
  it("collects an origin and starts a pinned git acquisition", async () => {
    const user = userEvent.setup();
    const panelProps = props();
    renderWithShell(<SourceAcquisitionContent {...panelProps} />, { reeId: "ree-1" });

    await user.type(screen.getByLabelText("Origin URL"), "https://example.test/repo.git");
    await user.selectOptions(screen.getByLabelText("Origin type"), "git");
    await user.type(screen.getByLabelText("Revision"), "v1.0.0");
    await user.click(screen.getByRole("button", { name: "Download source to workspace" }));
    expect(panelProps.commands.onDownloadSourceFiles).toHaveBeenCalledWith(
      "git",
      "https://example.test/repo.git",
      "v1.0.0",
    );
  });

  it("shows and clears an acquired uploaded source", async () => {
    const user = userEvent.setup();
    const panelProps = props({
      ree: { ...exampleEditorRee, originUrl: "", sourceType: "", resolvedRevision: "" },
      workspaceRemote: {
        workspaceSourceState: {
          sourceAvailable: true,
          sourceIncluded: true,
          sourceAcquiredBy: "upload",
          uploadedArchive: "source.zip",
        },
        sourceRepo: { name: "source.zip", acquiredBy: "upload", sourceType: "archive" },
      },
    });
    renderWithShell(<SourceAcquisitionContent {...panelProps} />, { reeId: "ree-1" });

    expect(screen.getByText("Source arrived from an uploaded archive.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear source" }));
    expect(panelProps.commands.onRemoveWorkspaceSource).toHaveBeenCalledOnce();
  });
});
