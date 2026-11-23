import { type Page, test } from "@playwright/test";

export async function stepShot(page: Page, name: string, timing: "before" | "after") {
  const info = test.info();
  let state = shotStates.get(info);
  if (!state) {
    state = { pages: [], counters: new WeakMap() };
    shotStates.set(info, state);
  }

  let pageIndex = state.pages.indexOf(page);
  if (pageIndex === -1) {
    pageIndex = state.pages.length;
    state.pages.push(page);
  }

  let seq: number;
  if (timing === "before") {
    seq = (state.counters.get(page) ?? 0) + 1;
    state.counters.set(page, seq);
  } else {
    seq = state.counters.get(page) ?? 1;
  }

  const slug =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "step";
  const lane = pageIndex === 0 ? "" : `${String.fromCharCode(97 + pageIndex)}-`;
  const file = `${lane}${String(seq).padStart(2, "0")}-${slug}-${timing}.png`;

  await page.screenshot({ path: info.outputPath(file) });
}

interface ShotState {
  pages: Page[];
  counters: WeakMap<Page, number>;
}

const shotStates = new WeakMap<ReturnType<typeof test.info>, ShotState>();
