import { describe, expect, it } from "vitest";
import { nextRunLogCursor } from "./client";

describe("nextRunLogCursor", () => {
  it("uses the backend cursor when another page is available", () => {
    expect(nextRunLogCursor("20", [{ seq: 19 }], "10")).toBe("20");
  });

  it("advances to the last seen log sequence at the current end of the feed", () => {
    expect(nextRunLogCursor(undefined, [{ seq: 1 }, { seq: 2 }], undefined)).toBe("2");
  });

  it("keeps the current cursor when polling returns no new lines", () => {
    expect(nextRunLogCursor(undefined, [], "2")).toBe("2");
  });
});
