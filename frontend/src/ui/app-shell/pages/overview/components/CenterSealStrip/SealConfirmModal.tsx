import { C } from "../../../../../theme/theme";
import { SealConfirmActions } from "./SealConfirmActions";
import { SealConfirmCopy } from "./SealConfirmCopy";
import { SealConfirmHeader } from "./SealConfirmHeader";
import { SealConfirmWarning } from "./SealConfirmWarning";

interface LevelMeta {
  color: string;
  label: string;
}

interface SealConfirmModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  missing: { key: string; label: string }[];
  allLive: boolean;
  level: number;
  totalCables: number;
  currentLevelMeta: LevelMeta;
}

export function SealConfirmModal({
  open,
  onClose,
  onConfirm,
  missing,
  allLive,
  level,
  totalCables,
  currentLevelMeta,
}: SealConfirmModalProps) {
  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.45)",
        backdropFilter: "blur(3px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <button
        type="button"
        aria-label="Close confirmation"
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          border: "none",
          background: "transparent",
          padding: 0,
          margin: 0,
          cursor: "default",
        }}
      />
      <div
        style={{
          background: C.surface,
          borderRadius: 14,
          width: 380,
          maxWidth: "90vw",
          border: `1.5px solid ${C.border}`,
          boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
          overflow: "hidden",
          position: "relative",
          zIndex: 1,
        }}
      >
        <SealConfirmHeader color={currentLevelMeta.color} />

        {!allLive && <SealConfirmWarning missing={missing} />}

        <SealConfirmCopy
          allLive={allLive}
          level={level}
          totalCables={totalCables}
          currentLabel={currentLevelMeta.label}
        />

        <SealConfirmActions
          onClose={onClose}
          onConfirm={onConfirm}
          confirmLabel={allLive ? "Seal REE" : "Seal anyway"}
          confirmColor={currentLevelMeta.color}
        />
      </div>
    </div>
  );
}
