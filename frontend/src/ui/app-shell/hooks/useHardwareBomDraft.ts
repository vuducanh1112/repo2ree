import type React from "react";
import { useEffect, useRef, useState } from "react";
import {
  draftFromHBOM,
  type HardwareBomDraft,
  hbomFromDraft,
  hbomSyncKey,
} from "../../../domain/hbom/hardwareBomDraft";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";

interface UseHardwareBomDraftArgs {
  ree: ReeDraftViewModel;
  onReeChange: React.Dispatch<React.SetStateAction<ReeDraftViewModel>>;
}

export function useHardwareBomDraft({ ree, onReeChange }: UseHardwareBomDraftArgs) {
  const [draft, setDraft] = useState<HardwareBomDraft>(() =>
    draftFromHBOM(ree.hardware_description),
  );
  const pendingLocalHbomKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const incomingKey = hbomSyncKey(ree.hardware_description);
    if (pendingLocalHbomKeyRef.current === incomingKey) {
      pendingLocalHbomKeyRef.current = null;
      return;
    }
    setDraft((previous) => draftFromHBOM(ree.hardware_description, previous));
  }, [ree.hardware_description]);

  const updateDraft = (nextDraft: HardwareBomDraft) => {
    const nextHBOM = hbomFromDraft(nextDraft, ree.hardware_description);
    pendingLocalHbomKeyRef.current = hbomSyncKey(nextHBOM);
    setDraft(nextDraft);
    onReeChange({
      ...ree,
      hardware_description: nextHBOM,
    });
  };

  return {
    draft,
    updateDraft,
  };
}
