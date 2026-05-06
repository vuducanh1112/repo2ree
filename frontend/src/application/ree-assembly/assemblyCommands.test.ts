import { describe, expect, it } from "vitest";
import { nonAssemblyPlanToCommands } from "./assemblyCommands";

describe("serviceRunCommands", () => {
  it("plans manual artifact effects in state-before-toast order", () => {
    const commands = nonAssemblyPlanToCommands({
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
