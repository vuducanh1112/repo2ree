import { describe, expect, it } from "vitest";
import { createStepCommandPlanners, nonStepPlanToCommands } from "./stepCommands";

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

  it("adapts every executable step plan into editor commands", () => {
    const planners = createStepCommandPlanners({
      ree: { runtime: "runtime.tar" },
      clock: { nowIso: () => "2026-01-01T00:00:00Z", nowMillis: () => 42 },
    });
    const commands = [
      ...planners.build({} as never),
      ...planners.hbom({} as never),
      ...planners.sbom({} as never),
      ...planners.activation({} as never),
      ...planners.evaluate({ strict: true }),
    ];
    expect(commands.filter((command) => command.type === "toast")).toHaveLength(5);
    expect(commands.length).toBeGreaterThan(5);
  });

  it("omits absent optional non-step effects", () => {
    expect(nonStepPlanToCommands({})).toEqual([]);
  });
});
