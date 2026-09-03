import { describe, expect, it } from "vitest";
import {
  activeImageId,
  CUSTOM_IMAGE_ID,
  DEFAULT_IMAGE_SELECTION,
  resolveWorkbenchImage,
} from "./imageSelection";
import type { WorkbenchImage } from "./Lab";

const images: WorkbenchImage[] = [
  { id: "standard", ref: "docker.io/library/docker:29-dind", label: "Standard", description: "" },
  { id: "python", ref: "docker.io/library/python:3.11-slim", label: "Python", description: "" },
];

describe("activeImageId", () => {
  it("reads the lab's first entry as chosen before anything is picked", () => {
    // It has to agree with the backend, which resolves a blank image to exactly
    // that entry — otherwise the highlighted card is not the image provisioned.
    expect(activeImageId(DEFAULT_IMAGE_SELECTION, images)).toBe("standard");
  });

  it("follows the author's pick once there is one", () => {
    expect(activeImageId({ selectedId: "python", customRef: "" }, images)).toBe("python");
    expect(activeImageId({ selectedId: CUSTOM_IMAGE_ID, customRef: "" }, images)).toBe("custom");
  });

  it("has nothing to highlight at a lab that offers no images", () => {
    expect(activeImageId(DEFAULT_IMAGE_SELECTION, [])).toBe("");
  });
});

describe("resolveWorkbenchImage", () => {
  it("sends nothing until the author picks, so the lab keeps its own default", () => {
    expect(resolveWorkbenchImage(DEFAULT_IMAGE_SELECTION, images)).toBe("");
  });

  it("sends the ref of the chosen catalog entry", () => {
    expect(resolveWorkbenchImage({ selectedId: "python", customRef: "" }, images)).toBe(
      "docker.io/library/python:3.11-slim",
    );
  });

  it("sends the typed ref, trimmed, when Custom is chosen", () => {
    expect(
      resolveWorkbenchImage(
        { selectedId: CUSTOM_IMAGE_ID, customRef: " ghcr.io/me/b:v3 " },
        images,
      ),
    ).toBe("ghcr.io/me/b:v3");
  });

  it("resolves a blank custom ref to nothing rather than to a guess", () => {
    // The drawer holds the provision button on this; resolving it to the lab
    // default here would provision an image the author did not ask for.
    expect(resolveWorkbenchImage({ selectedId: CUSTOM_IMAGE_ID, customRef: "   " }, images)).toBe(
      "",
    );
  });

  it("ignores a selection naming an entry the lab no longer offers", () => {
    expect(resolveWorkbenchImage({ selectedId: "retired", customRef: "" }, images)).toBe("");
  });
});
