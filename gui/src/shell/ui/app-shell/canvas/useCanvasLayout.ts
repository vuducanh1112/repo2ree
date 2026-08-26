import {
  type CanvasLayout,
  DEFAULT_LAYOUT,
  isDefaultLayout,
  type NodeOffset,
  parseStoredLayout,
  serializeLayout,
  withNodeMoved,
} from "@core/canvas/canvasLayout";
import { useCallback, useState } from "react";

const STORAGE_PREFIX = "repo2ree.canvasLayout";

/**
 * Where a user has arranged this REE's panels.
 *
 * Kept in `localStorage`, not in the REE. An arrangement is how one person
 * likes to look at a bench; the REE is the thing being authored, and a viewing
 * preference has no business travelling inside a sealed artifact or being
 * fought over by two authors of the same REE.
 *
 * Every storage access is guarded. `localStorage` throws outright in a browser
 * set to block site data, and a canvas that will not render because it could
 * not read a cosmetic preference is a worse failure than an un-arranged canvas.
 */
function storageKey(reeId: string): string {
  return `${STORAGE_PREFIX}.${reeId}`;
}

function readLayout(reeId: string): CanvasLayout {
  try {
    return parseStoredLayout(window.localStorage.getItem(storageKey(reeId)));
  } catch {
    return DEFAULT_LAYOUT;
  }
}

function writeLayout(reeId: string, layout: CanvasLayout): void {
  try {
    if (isDefaultLayout(layout)) window.localStorage.removeItem(storageKey(reeId));
    else window.localStorage.setItem(storageKey(reeId), serializeLayout(layout));
  } catch {
    // A layout that cannot be saved is still worth using for this session.
  }
}

interface CanvasLayoutHandle {
  layout: CanvasLayout;
  /** Commit a panel's new offset. Called once a drag or nudge settles. */
  moveNode: (key: string, offset: NodeOffset) => void;
  resetLayout: () => void;
  isDefault: boolean;
}

export function useCanvasLayout(reeId: string): CanvasLayoutHandle {
  // Read once on mount rather than in an effect: the canvas should paint in the
  // arrangement the user left it in, not jump into it a frame later.
  const [layout, setLayout] = useState<CanvasLayout>(() => readLayout(reeId));

  const moveNode = useCallback(
    (key: string, offset: NodeOffset) => {
      setLayout((previous) => {
        const next = withNodeMoved(previous, key, offset);
        writeLayout(reeId, next);
        return next;
      });
    },
    [reeId],
  );

  const resetLayout = useCallback(() => {
    setLayout(() => {
      writeLayout(reeId, DEFAULT_LAYOUT);
      return DEFAULT_LAYOUT;
    });
  }, [reeId]);

  return { layout, moveNode, resetLayout, isDefault: isDefaultLayout(layout) };
}
