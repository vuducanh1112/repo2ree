import { describe, expect, it } from "vitest";
import type { Lab } from "./Lab";
import { sortLabs } from "./Lab";

function lab(overrides: Partial<Lab> = {}): Lab {
  return {
    id: "a1",
    label: "Worker",
    description: "",
    lifecycleMode: "provider_managed",
    profiles: [],
    status: "connected",
    available: true,
    ...overrides,
  };
}

describe("sortLabs", () => {
  it("orders by label then id without mutating the input", () => {
    const input = [
      lab({ id: "z", label: "Beta" }),
      lab({ id: "a", label: "Alpha" }),
      lab({ id: "b", label: "Alpha" }),
    ];
    const sorted = sortLabs(input);
    expect(sorted.map((location) => location.id)).toEqual(["a", "b", "z"]);
    expect(input[0]?.id).toBe("z");
  });
});
