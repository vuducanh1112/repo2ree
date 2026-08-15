import { PAGE } from "@core/app-shell/pages";
import { createInitialState } from "@shell/ui/app-shell/state/appShellReducer";
import { describe, expect, it, vi } from "vitest";
import { createReeEditorCommands } from "./createReeEditorCommands";

describe("createReeEditorCommands", () => {
  it("adapts UI setters and imperative commands to their owners", async () => {
    const state = createInitialState();
    const dispatch = vi.fn();
    const delegates = {
      runAction: vi.fn().mockResolvedValue(undefined),
      runStep: vi.fn().mockResolvedValue(undefined),
      cancelAction: vi.fn().mockResolvedValue(undefined),
      persistWorkspaceFile: vi.fn().mockResolvedValue(undefined),
      handleDownloadRee: vi.fn(),
      handleSealRee: vi.fn().mockResolvedValue(undefined),
      handleDownloadSourceFiles: vi.fn().mockResolvedValue(undefined),
      handleWorkspaceUpload: vi.fn(),
      handleRemoveWorkspaceSource: vi.fn(),
      downloadWorkspaceFile: vi.fn().mockResolvedValue(undefined),
      flushReeIntent: vi.fn().mockResolvedValue(undefined),
    };
    const commands = createReeEditorCommands({
      reeIntent: state.reeIntent,
      reeSession: state.reeSession,
      stepRuns: state.stepRuns,
      uiChrome: state.uiChrome,
      dispatch,
      ...delegates,
    });

    commands.setPage(PAGE.BUILD);
    commands.setReeSpec((current) => ({ ...current, name: "Updated" }));
    commands.setWorkspaceSourceState({ sourceAvailable: true });
    commands.setArtifactStatus({ runtimeIncluded: true });
    commands.setEvaluationState({ dependencyLevel: 2 });
    commands.setLocked((current) => !current);
    commands.setRepoMode((current) => (current === "url" ? "upload" : "url"));
    commands.setFocusedField(() => "name");
    commands.setStepParams((current) => current);
    commands.setFilesConsoleOpen(true);
    commands.clearToast();
    commands.onSeal({ includeSource: true, includeRuntime: false, includeResults: true });
    commands.onDownloadRee();
    await commands.onDownloadSourceFiles("git", "https://example.test/repo.git");
    commands.onWorkspaceUpload({ mode: "archive", archiveName: "source.tgz" });
    commands.onRemoveWorkspaceSource();
    await commands.onDownloadWorkspaceFile("README.md");
    await commands.onRunAction("build", {});
    await commands.onCancelAction("build");
    await commands.onRunStep("build", {});
    await commands.onPersistWorkspaceFile(undefined, "run.sh", "echo ok");
    await commands.flushReeIntent();

    expect(dispatch.mock.calls.map(([action]) => action.type)).toEqual([
      "patch",
      "updateReeSpec",
      "setWorkspaceSourceState",
      "setArtifactStatus",
      "setEvaluationState",
      "setLocked",
      "setRepoMode",
      "patch",
      "setStepParams",
      "patch",
      "clearToast",
    ]);
    expect(delegates.handleSealRee).toHaveBeenCalledOnce();
    expect(delegates.runAction).toHaveBeenCalledWith("build", {});
    expect(delegates.runStep).toHaveBeenCalledWith("build", {});
    expect(delegates.persistWorkspaceFile).toHaveBeenCalledWith(undefined, "run.sh", "echo ok");
  });
});
