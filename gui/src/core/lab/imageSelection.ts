import type { WorkbenchImage } from "./Lab";

export interface WorkbenchImageSelection {
  /** One of the lab's image ids, or "" to mean "the lab's default". */
  selectedId: string;
}

export const DEFAULT_IMAGE_SELECTION: WorkbenchImageSelection = { selectedId: "" };

/**
 * Which option reads as chosen. Before the user picks anything that is the
 * lab's first image — the same one the backend resolves a blank image to, so
 * the highlighted card is never a different image from the one the REE declares.
 */
export function activeImageId(
  selection: WorkbenchImageSelection,
  images: readonly WorkbenchImage[],
): string {
  return selection.selectedId || images[0]?.id || "";
}

/** The image ref to send. "" means "let the lab use its own default": nothing picked yet. */
export function resolveWorkbenchImage(
  selection: WorkbenchImageSelection,
  images: readonly WorkbenchImage[],
): string {
  return images.find((image) => image.id === selection.selectedId)?.ref ?? "";
}
