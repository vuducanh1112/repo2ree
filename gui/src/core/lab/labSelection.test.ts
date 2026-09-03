import { describe, expect, it } from "vitest";
import type { Lab } from "./Lab";
import { selectLabPage } from "./labSelection";

function lab(overrides: Partial<Lab> = {}): Lab {
  return {
    id: "a1",
    label: "worker",
    description: "",
    lifecycleMode: "provider_managed",
    images: [],
    acceptsCustomImage: false,
    status: "connected",
    available: true,
    ...overrides,
  };
}

/** `count` labs named lab-01, lab-02, … with matching ids. */
function fleet(count: number): Lab[] {
  return Array.from({ length: count }, (_, index) => {
    const n = String(index + 1).padStart(2, "0");
    return lab({ id: `lab-${n}`, label: `lab-${n}` });
  });
}

const at = (query = "", page = 0) => ({ query, page });

describe("selectLabPage", () => {
  it("reports one empty page for an empty fleet", () => {
    const view = selectLabPage([], at());
    expect(view.visible).toEqual([]);
    expect(view.matches).toEqual([]);
    expect(view.pageCount).toBe(1);
    expect(view.page).toBe(0);
  });

  it("widens the grid as the result set grows", () => {
    // Two columns keeps a pair of labs from stretching across the deck; the
    // grid only reaches its full width once there is something to fill it.
    expect(selectLabPage(fleet(2), at()).columns).toBe(2);
    expect(selectLabPage(fleet(3), at()).columns).toBe(3);
    expect(selectLabPage(fleet(6), at()).columns).toBe(3);
    expect(selectLabPage(fleet(7), at()).columns).toBe(4);
  });

  it("fills two rows per page and reports the page count", () => {
    const view = selectLabPage(fleet(12), at());
    expect(view.columns).toBe(4);
    expect(view.visible).toHaveLength(8);
    expect(view.pageCount).toBe(2);
    expect(view.visible[0].label).toBe("lab-01");
  });

  it("slices the requested page", () => {
    const view = selectLabPage(fleet(12), at("", 1));
    expect(view.page).toBe(1);
    expect(view.visible).toHaveLength(4);
    expect(view.visible[0].label).toBe("lab-09");
  });

  it("matches location label and id, case-insensitively and trimmed", () => {
    const labs = [lab({ id: "lab-oslo", label: "lab-oslo-01" }), ...fleet(3)];
    expect(selectLabPage(labs, at("  OSLO ")).matches).toHaveLength(1);
    expect(selectLabPage(labs, at("LAB-OSLO")).matches).toHaveLength(1);
    expect(selectLabPage(labs, at("nothing")).matches).toEqual([]);
  });

  it("clamps the page when a filter shrinks the list under it", () => {
    // The user is deep in a large fleet and then types a filter: the page they
    // were standing on no longer exists, and the grid must not go blank.
    const view = selectLabPage(fleet(40), at("lab-07", 3));
    expect(view.matches).toHaveLength(1);
    expect(view.page).toBe(0);
    expect(view.visible).toHaveLength(1);
  });

  it("clamps a negative page", () => {
    expect(selectLabPage(fleet(4), at("", -2)).page).toBe(0);
  });

  it("leaves the given order alone", () => {
    const labs = [lab({ id: "b", label: "zeta" }), lab({ id: "a", label: "alpha" })];
    expect(selectLabPage(labs, at()).visible.map((one) => one.label)).toEqual(["zeta", "alpha"]);
  });
});
