import { PAGE } from "@core/app-shell/pages";
import { appShellReducer, createInitialState } from "@shell/state/ree-editor/store/appShellReducer";
import type { AppShellAction } from "@shell/state/ree-editor/store/types";
import { describe, expect, it, vi } from "vitest";
import { createReeEditorCommands } from "./createReeEditorCommands";

function commandDelegates() {
  return {
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
}

describe("createReeEditorCommands", () => {
  it("adapts UI setters and imperative commands to their owners", async () => {
    const dispatch = vi.fn();
    const delegates = commandDelegates();
    const commands = createReeEditorCommands({
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
    commands.setReceiptsConsoleOpen(true);
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
      "setFocusedField",
      "setStepParams",
      "patch",
      "patch",
      "clearToast",
    ]);
    expect(delegates.handleSealRee).toHaveBeenCalledOnce();
    expect(delegates.runAction).toHaveBeenCalledWith("build", {});
    expect(delegates.runStep).toHaveBeenCalledWith("build", {});
    expect(delegates.persistWorkspaceFile).toHaveBeenCalledWith(undefined, "run.sh", "echo ok");
  });

  it("composes functional updates against reducer-current state", () => {
    let state = createInitialState();
    const dispatch = (action: AppShellAction) => {
      state = appShellReducer(state, action);
    };
    const commands = createReeEditorCommands({ dispatch, ...commandDelegates() });

    commands.setReeSpec((current) => ({ ...current, name: "first update" }));
    commands.setReeSpec((current) => ({
      ...current,
      catalogMetadata: { ...current.catalogMetadata, version: "2" },
    }));
    commands.setLocked((current) => !current);
    commands.setLocked((current) => !current);
    commands.setStepParams(createInitialState().stepRuns.stepParams);

    expect(state.reeIntent.reeSpec.name).toBe("first update");
    expect(state.reeIntent.reeSpec.catalogMetadata.version).toBe("2");
    expect(state.uiChrome.locked).toBe(false);
    expect(state.stepRuns.stepParams.build).toEqual({});
  });

  it("keeps each canvas window's position, size, and close behavior independent", () => {
    let state = createInitialState();
    const dispatch = (action: AppShellAction) => {
      state = appShellReducer(state, action);
    };
    const commands = createReeEditorCommands({ dispatch, ...commandDelegates() });

    commands.setPage(PAGE.METADATA);
    commands.setPageWindowPosition(PAGE.METADATA, { x: 120, y: 80 });
    commands.setPageWindowSize(PAGE.METADATA, { width: 820, height: 600 });
    commands.setPage(PAGE.HBOM);

    expect(state.uiChrome.openPages).toEqual([
      {
        page: PAGE.METADATA,
        position: { x: 120, y: 80 },
        size: { width: 820, height: 600 },
      },
      { page: PAGE.HBOM, position: null },
    ]);

    commands.closePage(PAGE.METADATA);
    expect(state.uiChrome.page).toBe(PAGE.HBOM);
    expect(state.uiChrome.openPages).toEqual([{ page: PAGE.HBOM, position: null }]);

    commands.closePage(PAGE.HBOM);
    expect(state.uiChrome.page).toBe(PAGE.CANVAS);
    expect(state.uiChrome.openPages).toEqual([]);
  });
});
