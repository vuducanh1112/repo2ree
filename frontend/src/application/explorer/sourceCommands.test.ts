import { describe, expect, it } from "vitest";
import type { Ree } from "../../types";
import { sourceChangeResetCommands, sourceFailureCommands } from "./sourceCommands";

const ree = { name: "demo" } as Ree;

describe("sourceCommands", () => {
  it("plans reset and toast commands when source changes visibly", () => {
    const commands = sourceChangeResetCommands();

    expect(commands).toHaveLength(2);
    expect(commands[0].type).toBe("resetWorkflowOnSourceChange");
    expect(commands[1]).toEqual({
      type: "toast",
      message: "Source changed — workflow status and scripts reset",
      toastType: "info",
    });
  });

  it("omits reset toast when source change is silent", () => {
    const commands = sourceChangeResetCommands({ silent: true });

    expect(commands).toHaveLength(1);
    expect(commands[0].type).toBe("resetWorkflowOnSourceChange");
  });

  it("plans source failure outcome before error toast", () => {
    const commands = sourceFailureCommands({ ree, message: "Source failed" });

    expect(commands.map((command) => command.type)).toEqual(["applySourceOutcome", "toast"]);
    expect(commands[1]).toEqual({
      type: "toast",
      message: "Source failed",
      toastType: "error",
    });
  });
});
