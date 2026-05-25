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
  totalCables: number;
  currentLevelMeta: LevelMeta;
}

export function SealConfirmModal({
  open,
  onClose,
  onConfirm,
  missing,
  allLive,
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
          background: "rgba(255, 255, 255, 0.92)",
          backdropFilter: "blur(18px)",
          borderRadius: 14,
          width: 380,
          maxWidth: "90vw",
          border: "1px solid rgba(125, 211, 252, 0.58)",
          boxShadow: "0 24px 70px rgba(15, 23, 42, 0.28)",
          overflow: "hidden",
          position: "relative",
          zIndex: 1,
        }}
      >
        <SealConfirmHeader color={currentLevelMeta.color} />

        {!allLive && <SealConfirmWarning missing={missing} />}

        <SealConfirmCopy
          allLive={allLive}
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
