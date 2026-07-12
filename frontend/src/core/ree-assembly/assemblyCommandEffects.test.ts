import { describe, expect, it } from "vitest";
import { createEmptyReeSpec } from "../ree/ReeSpec";
import { mapAssemblyCommandsToEffects, mapSourceCommandsToEffects } from "./assemblyCommandEffects";

describe("mapAssemblyCommandsToEffects", () => {
  it("maps persist commands into shell persistence effects", () => {
    expect(
      mapAssemblyCommandsToEffects([{ type: "persistFile", path: "sbom.json", content: "{}" }]),
    ).toEqual([{ type: "persistFile", path: "sbom.json", content: "{}" }]);
  });

  it("maps toast commands into shell toast effects", () => {
    expect(
      mapAssemblyCommandsToEffects([
        { type: "toast", message: "Build complete", toastType: "success" },
      ]),
    ).toEqual([{ type: "toast", message: "Build complete", toastType: "success" }]);
  });

  it("drops hydrateWorkspace commands with no state updates (files come from React Query)", () => {
    const effects = mapAssemblyCommandsToEffects([
      {
        type: "hydrateWorkspace",
        workspaceFiles: [],
        reeArtifactFiles: [],
        reeSpec: undefined,
      },
    ]);

    expect(effects).toHaveLength(0);
  });

  it("maps hydrateWorkspace with reeSpec into dispatchStateCommand", () => {
    const effects = mapAssemblyCommandsToEffects([
      {
        type: "hydrateWorkspace",
        workspaceFiles: [],
        reeArtifactFiles: [],
        reeSpec: {
          ...createEmptyReeSpec(),
          name: "test",
        },
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

  it("drops setSourceLog commands (logs now come from React Query)", () => {
    const effects = mapSourceCommandsToEffects([
      {
        type: "setSourceLog",
        lines: [{ type: "info", msg: "downloading" }],
        ts: "2026-01-01T00:00:00Z",
      },
    ]);

    expect(effects).toHaveLength(0);
  });
});
