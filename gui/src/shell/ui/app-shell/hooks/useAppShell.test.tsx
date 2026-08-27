import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAppShell } from "./useAppShell";

const mocks = vi.hoisted(() => ({
  dispatch: vi.fn(),
  useReeEditor: vi.fn(),
  state: {
    reeIntent: { reeSpec: { name: "test" } },
    stepRuns: { badges: {} },
    uiChrome: { page: "canvas" },
  },
  editor: {
    model: { provisioned: true, ree: { artifact: {} } },
    sync: { isReeIntentDirty: false },
    commands: { setPage: vi.fn() },
    seal: { running: false, log: null },
  },
}));

vi.mock("@shell/state/ree-editor/hooks/useReeEditor", () => ({
  useReeEditor: mocks.useReeEditor,
}));
vi.mock("../providers/AppShellProvider", () => ({
  useAppShellContext: () => ({ state: mocks.state, dispatch: mocks.dispatch }),
}));

describe("useAppShell", () => {
  beforeEach(() => {
    mocks.useReeEditor.mockReset().mockReturnValue(mocks.editor);
  });

  it("composes editor runtime groups with shell chrome", () => {
    const { result } = renderHook(() => useAppShell());

    expect(mocks.useReeEditor).toHaveBeenCalledWith({
      reeIntent: mocks.state.reeIntent,
      stepRuns: mocks.state.stepRuns,
      dispatch: mocks.dispatch,
    });
    expect(result.current).toEqual({
      ...mocks.editor,
      chrome: { ...mocks.state.uiChrome, locked: false },
    });
  });
});
