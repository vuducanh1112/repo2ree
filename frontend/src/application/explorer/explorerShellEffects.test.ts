import { describe, expect, it } from "vitest";
import { mapServiceRunCommandsToEffects, mapSourceCommandsToEffects } from "./explorerShellEffects";

describe("mapServiceRunCommandsToEffects", () => {
  it("maps persist commands into shell persistence effects", () => {
    expect(
      mapServiceRunCommandsToEffects([{ type: "persistFile", path: "sbom.json", content: "{}" }]),
    ).toEqual([{ type: "persistFile", path: "sbom.json", content: "{}" }]);
  });

  it("maps toast commands into shell toast effects", () => {
    expect(
      mapServiceRunCommandsToEffects([
        { type: "toast", message: "Build complete", toastType: "success" },
      ]),
    ).toEqual([{ type: "toast", message: "Build complete", toastType: "success" }]);
  });

  it("maps stateful service commands into dispatch actions", () => {
    const effects = mapServiceRunCommandsToEffects([
      {
        type: "hydrateWorkspace",
        virtualFiles: [],
        workspaceReeFiles: [],
        ree: undefined,
      },
    ]);

    expect(effects).toHaveLength(1);
    expect(effects[0]?.type).toBe("dispatchStateCommand");
  });
});

describe("mapSourceCommandsToEffects", () => {
  it("maps source toasts into shell toast effects", () => {
    expect(
      mapSourceCommandsToEffects([{ type: "toast", message: "Source changed", toastType: "info" }]),
    ).toEqual([{ type: "toast", message: "Source changed", toastType: "info" }]);
  });

  it("maps source state commands into dispatch actions", () => {
    const effects = mapSourceCommandsToEffects([
      {
        type: "setSourceLog",
        lines: [{ type: "info", msg: "downloading" }],
        ts: "2026-01-01T00:00:00Z",
      },
    ]);

    expect(effects).toHaveLength(1);
    expect(effects[0]?.type).toBe("dispatchStateCommand");
  });
});
