import { Ic } from "@shell/ui/shared/components/Icon";
import type React from "react";
import styles from "./SourceRuntime.module.css";

interface SourceUploadDropzoneProps {
  dragging: boolean;
  inputDisabled: boolean;
  onDragOver: (event: React.DragEvent<HTMLButtonElement>) => void;
  onDragLeave: () => void;
  onDrop: (event: React.DragEvent<HTMLButtonElement>) => void;
  onClick: () => void;
}

export function SourceUploadDropzone({
  dragging,
  inputDisabled,
  onDragOver,
  onDragLeave,
  onDrop,
  onClick,
}: SourceUploadDropzoneProps) {
  return (
    <button
      type="button"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={onClick}
      disabled={inputDisabled}
      className={styles.dropzone}
      data-dragging={dragging || undefined}
    >
      <span aria-hidden className={styles.dropIcon}>
        {Ic.upload(18)}
      </span>
      <span className={styles.dropPrompt}>
        Drop archive or <span className={styles.dropAction}>browse archive</span>
      </span>
      <span className={styles.dropFormats}>.zip · .tar · .tar.gz</span>
    </button>
  );
}
