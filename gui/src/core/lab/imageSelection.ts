import type { WorkbenchImage } from "./Lab";

// Reserved selection id for "provide your own reference"; never a catalog id.
export const CUSTOM_IMAGE_ID = "custom";

export interface WorkbenchImageSelection {
  /** A catalog image id, {@link CUSTOM_IMAGE_ID}, or "" to mean "the lab's default". */
  selectedId: string;
  customRef: string;
}

export const DEFAULT_IMAGE_SELECTION: WorkbenchImageSelection = {
  selectedId: "",
  customRef: "",
};

/**
 * Which option reads as chosen. Before the user picks anything that is the
 * lab's first catalog entry — the same one the backend resolves a blank image
 * to, so the highlighted card is never a different image from the one that
 * would actually be provisioned.
 */
export function activeImageId(
  selection: WorkbenchImageSelection,
  images: readonly WorkbenchImage[],
): string {
  return selection.selectedId || images[0]?.id || "";
}

/**
 * The image ref to send. "" means "let the lab use its own default": nothing
 * picked yet, or Custom selected but left blank.
 */
export function resolveWorkbenchImage(
  selection: WorkbenchImageSelection,
  images: readonly WorkbenchImage[],
): string {
  if (selection.selectedId === CUSTOM_IMAGE_ID) {
    return selection.customRef.trim();
  }
  return images.find((image) => image.id === selection.selectedId)?.ref ?? "";
}
