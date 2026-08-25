import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { Point } from "@core/canvas/cableGeometry";
import type { WindowSize } from "@core/canvas/nodeWindowPlacement";

// Which pages have a window on the canvas, and where each one stands. The hub
// canvas is the ground the windows sit on rather than a window itself, so it is
// never a member.

export interface OpenPageWindow {
  page: AppShellPage;
  /** User-selected screen-space size; absent means the standard window size. */
  size?: WindowSize;
  /**
   * Where the window stands on the canvas, in camera-local space — not on
   * screen. Panning moves the view, not the window, so this is what lets a
   * window be left behind and come back to exactly where it was put.
   *
   * Null until the canvas has measured a first position for it: opening is a
   * store decision, but where a window lands depends on geometry only the
   * rendered canvas knows.
   */
  position: Point | null;
}

/** Add a page to the open set, keeping the existing order. */
export function openPageList(
  openPages: readonly OpenPageWindow[],
  page: AppShellPage,
): OpenPageWindow[] {
  if (page === PAGE.CANVAS || openPages.some((open) => open.page === page)) return [...openPages];
  return [...openPages, { page, position: null }];
}

/** Remove a page from the open set. */
export function closePageList(
  openPages: readonly OpenPageWindow[],
  page: AppShellPage,
): OpenPageWindow[] {
  return openPages.filter((open) => open.page !== page);
}

/** Record where a window stands, whether it was just placed or just dragged. */
export function positionPageWindow(
  openPages: readonly OpenPageWindow[],
  page: AppShellPage,
  position: Point,
): OpenPageWindow[] {
  return openPages.map((open) => (open.page === page ? { ...open, position } : open));
}

/** Record an independently resized window without changing its position or siblings. */
export function sizePageWindow(
  openPages: readonly OpenPageWindow[],
  page: AppShellPage,
  size: WindowSize,
): OpenPageWindow[] {
  return openPages.map((open) => (open.page === page ? { ...open, size } : open));
}

/** The position recorded for a page, if it has one yet. */
export function pageWindowPosition(
  openPages: readonly OpenPageWindow[],
  page: AppShellPage,
): Point | null {
  return openPages.find((open) => open.page === page)?.position ?? null;
}

/**
 * Where focus lands when the focused window closes: the most recently opened
 * window still standing, or the bare canvas once the last one goes. Closing a
 * window the user was not looking at leaves focus alone; that is the caller's
 * check, not this one's.
 */
export function nextFocusAfterClose(
  openPages: readonly OpenPageWindow[],
  closing: AppShellPage,
): AppShellPage {
  const remaining = closePageList(openPages, closing);
  return remaining[remaining.length - 1]?.page ?? PAGE.CANVAS;
}
