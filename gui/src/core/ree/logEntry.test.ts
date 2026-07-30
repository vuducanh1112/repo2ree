import { describe, expect, it } from "vitest";
import { appendLine } from "./logEntry";

describe("appendLine", () => {
  it("uses the timestamp supplied by the imperative shell", () => {
    const first = appendLine(null, "info", "starting", "2026-07-30T10:00:00.000Z");
    const second = appendLine(first, "ok", "done", "2026-07-30T10:00:01.000Z");

    expect(second).toEqual({
      lines: [
        { type: "info", msg: "starting", ts: "2026-07-30T10:00:00.000Z" },
        { type: "ok", msg: "done", ts: "2026-07-30T10:00:01.000Z" },
      ],
      ts: "2026-07-30T10:00:01.000Z",
    });
  });
});
