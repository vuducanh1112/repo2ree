import { describe, expect, it } from "vitest";
import { nonStepPlanToCommands } from "./stepCommands";

describe("serviceRunCommands", () => {
  it("plans manual artifact effects in state-before-toast order", () => {
    const commands = nonStepPlanToCommands({
      reeSpecPatch: { swhid: "swh:1:dir:abc" },
      lock: true,
      successMessage: "Archived",
    });

    expect(commands).toEqual([
      { type: "setReeSpec", reeSpec: { swhid: "swh:1:dir:abc" } },
      { type: "setLocked", locked: true },
      { type: "toast", message: "Archived", toastType: "success" },
    ]);
  });
});
