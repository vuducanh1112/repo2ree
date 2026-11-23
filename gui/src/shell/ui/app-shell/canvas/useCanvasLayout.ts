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
  } catch {}
}

interface CanvasLayoutHandle {
  layout: CanvasLayout;
  moveNode: (key: string, offset: NodeOffset) => void;
  resetLayout: () => void;
  isDefault: boolean;
}

export function useCanvasLayout(reeId: string): CanvasLayoutHandle {
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
