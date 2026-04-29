import { describe, expect, it } from "vitest";
import { nonWorkflowPlanToCommands } from "./workflowStepCommands";

describe("serviceRunCommands", () => {
  it("plans non-workflow effects in state-before-toast order", () => {
    const commands = nonWorkflowPlanToCommands({
      reePatch: { swhid: "swh:1:dir:abc" },
      lock: true,
      successMessage: "Archived",
    });

    expect(commands).toEqual([
      { type: "patchRee", patch: { swhid: "swh:1:dir:abc" } },
      { type: "setLocked", locked: true },
      { type: "toast", message: "Archived", toastType: "success" },
    ]);
  });
});
