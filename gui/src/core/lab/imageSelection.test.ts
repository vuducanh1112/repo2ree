import { describe, expect, it } from "vitest";
import { activeImageId, DEFAULT_IMAGE_SELECTION, resolveWorkbenchImage } from "./imageSelection";
import type { WorkbenchImage } from "./Lab";

const images: WorkbenchImage[] = [
  { id: "standard", ref: "docker.io/library/docker:29-dind", label: "Standard", description: "" },
  { id: "python", ref: "docker.io/library/python:3.11-slim", label: "Python", description: "" },
];

describe("activeImageId", () => {
  it("reads the lab's first entry as chosen before anything is picked", () => {
    // It has to agree with the backend, which resolves a blank image to exactly
    // that entry — otherwise the highlighted card is not the image declared.
    expect(activeImageId(DEFAULT_IMAGE_SELECTION, images)).toBe("standard");
  });

  it("follows the author's pick once there is one", () => {
    expect(activeImageId({ selectedId: "python" }, images)).toBe("python");
  });

  it("has nothing to highlight at a lab that offers no images", () => {
    expect(activeImageId(DEFAULT_IMAGE_SELECTION, [])).toBe("");
  });
});

describe("resolveWorkbenchImage", () => {
  it("sends nothing until the author picks, so the lab keeps its own default", () => {
    expect(resolveWorkbenchImage(DEFAULT_IMAGE_SELECTION, images)).toBe("");
  });

  it("sends the ref of the chosen entry", () => {
    expect(resolveWorkbenchImage({ selectedId: "python" }, images)).toBe(
      "docker.io/library/python:3.11-slim",
    );
  });

  it("ignores a selection naming an entry the lab no longer offers", () => {
    expect(resolveWorkbenchImage({ selectedId: "retired" }, images)).toBe("");
  });
});
