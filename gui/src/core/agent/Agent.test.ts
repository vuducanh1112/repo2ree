import { describe, expect, it } from "vitest";
import { type Agent, connectedDurationMs, formatDuration, sortAgents } from "./Agent";

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "a1",
    hostname: "worker",
    version: "0.1.0",
    dockerMode: "dind",
    connectedAt: "2026-07-01T00:00:00Z",
    status: "connected",
    ...overrides,
  };
}

describe("connectedDurationMs", () => {
  it("returns elapsed ms against the given clock", () => {
    const now = Date.parse("2026-07-01T00:00:30Z");
    expect(connectedDurationMs(agent(), now)).toBe(30_000);
  });

  it("clamps a future timestamp to 0", () => {
    const now = Date.parse("2026-06-30T23:59:00Z");
    expect(connectedDurationMs(agent(), now)).toBe(0);
  });

  it("returns 0 for an unparseable timestamp", () => {
    expect(connectedDurationMs(agent({ connectedAt: "nonsense" }), Date.now())).toBe(0);
  });
});

describe("formatDuration", () => {
  it("labels each magnitude band", () => {
    expect(formatDuration(45_000)).toBe("45s");
    expect(formatDuration(12 * 60_000)).toBe("12m");
    expect(formatDuration(3 * 3_600_000)).toBe("3h");
    expect(formatDuration(5 * 86_400_000)).toBe("5d");
  });
});

describe("sortAgents", () => {
  it("orders by hostname then id without mutating the input", () => {
    const input = [
      agent({ id: "z", hostname: "b" }),
      agent({ id: "a", hostname: "a" }),
      agent({ id: "b", hostname: "a" }),
    ];
    const sorted = sortAgents(input);
    expect(sorted.map((a) => a.id)).toEqual(["a", "b", "z"]);
    expect(input[0]?.id).toBe("z"); // original untouched
  });
});
