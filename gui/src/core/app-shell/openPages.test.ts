import { describe, expect, it } from "vitest";
import {
  closePageList,
  nextFocusAfterClose,
  type OpenPageWindow,
  openPageList,
  pageWindowPosition,
  positionPageWindow,
  sizePageWindow,
} from "./openPages";
import type { AppShellPage } from "./pages";
import { PAGE } from "./pages";

const open = (page: AppShellPage, position: OpenPageWindow["position"] = null) => ({
  page,
  position,
});

describe("openPageList", () => {
  it("appends a newly opened page, with its place on the canvas still unknown", () => {
    expect(openPageList([open(PAGE.METADATA)], PAGE.HBOM)).toEqual([
      open(PAGE.METADATA),
      open(PAGE.HBOM),
    ]);
  });

  it("keeps an already-open page where it is rather than reordering it", () => {
    // Re-focusing an open window must not move it, nor forget where it stands.
    const placed = open(PAGE.METADATA, { x: 300, y: 120 });
    expect(openPageList([placed, open(PAGE.HBOM)], PAGE.METADATA)).toEqual([
      placed,
      open(PAGE.HBOM),
    ]);
  });

  it("never opens a window for the canvas itself", () => {
    expect(openPageList([open(PAGE.METADATA)], PAGE.CANVAS)).toEqual([open(PAGE.METADATA)]);
  });
});

describe("closePageList", () => {
  it("removes only the named page", () => {
    expect(
      closePageList([open(PAGE.METADATA), open(PAGE.HBOM), open(PAGE.SEAL)], PAGE.HBOM),
    ).toEqual([open(PAGE.METADATA), open(PAGE.SEAL)]);
  });
});

describe("nextFocusAfterClose", () => {
  it("falls back to the most recently opened window still standing", () => {
    expect(
      nextFocusAfterClose([open(PAGE.METADATA), open(PAGE.HBOM), open(PAGE.SEAL)], PAGE.SEAL),
    ).toBe(PAGE.HBOM);
  });

  it("returns to the bare canvas once the last window closes", () => {
    expect(nextFocusAfterClose([open(PAGE.METADATA)], PAGE.METADATA)).toBe(PAGE.CANVAS);
  });
});

describe("positionPageWindow", () => {
  it("records where one window stands, leaving the others alone", () => {
    const before = [open(PAGE.METADATA), open(PAGE.HBOM, { x: 10, y: 10 })];
    const after = positionPageWindow(before, PAGE.METADATA, { x: 420, y: 260 });

    expect(pageWindowPosition(after, PAGE.METADATA)).toEqual({ x: 420, y: 260 });
    expect(pageWindowPosition(after, PAGE.HBOM)).toEqual({ x: 10, y: 10 });
  });

  it("reports no position for a page that is not open", () => {
    expect(pageWindowPosition([open(PAGE.METADATA)], PAGE.SEAL)).toBeNull();
  });
});

describe("sizePageWindow", () => {
  it("resizes only the named window", () => {
    const before = [open(PAGE.METADATA), open(PAGE.HBOM)];
    const after = sizePageWindow(before, PAGE.HBOM, { width: 860, height: 620 });

    expect(after[0]?.size).toBeUndefined();
    expect(after[1]?.size).toEqual({ width: 860, height: 620 });
  });
});
