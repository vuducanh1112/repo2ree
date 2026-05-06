import type React from "react";
import { useRef, useState } from "react";
import type { SourceUploadCommit } from "../../../../../core/ree/ReeTypes";
import { Ic } from "../../../shared/components/Icon";
import { C, S_SOURCE_UPLOAD_STATUS_LINE_BASE } from "../../../theme/theme";
import { SourceUploadCommitted } from "./SourceUploadCommitted";
import { SourceUploadDropzone } from "./SourceUploadDropzone";
import { SourceUploadPending } from "./SourceUploadPending";

interface SourceUploadFieldProps {
  locked: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onCommit: (payload: SourceUploadCommit) => void;
  committedName?: string;
}
export function SourceUploadField({
  locked,
  disabled = false,
  disabledReason,
  onCommit,
  committedName,
}: SourceUploadFieldProps) {
  const archiveRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState<SourceUploadCommit | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);
  const inputDisabled = locked || disabled;

  const handleArchive = (file: File) => {
    if (!file || inputDisabled) return;
    setDropError(null);
    setPending({ mode: "archive", archiveName: file.name, archiveFile: file });
  };

  const handleDrop = (dragEvent: React.DragEvent<HTMLElement>) => {
    dragEvent.preventDefault();
    setDragging(false);
    if (inputDisabled) return;
    const files = dragEvent.dataTransfer.files;
    if (!files || files.length === 0) return;
    if (files.length !== 1 || !/\.(zip|tar|tar\.gz|tgz)$/i.test(files[0].name)) {
      setDropError("Only a single tarball/archive upload is allowed for direct repo upload.");
      return;
    }
    handleArchive(files[0]);
  };

  const handleConfirm = () => {
    if (!pending) return;
    onCommit(pending);
    setPending(null);
  };

  const handleCancel = () => setPending(null);

  return (
    <div
      style={{
        padding: "8px 0 14px",
      }}
    >
      <input
        ref={archiveRef}
        type="file"
        accept=".zip,.tar,.gz,.tgz,.tar.gz"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) handleArchive(file);
          event.currentTarget.value = "";
        }}
        style={{
          display: "none",
        }}
      />

      {committedName && (
        <SourceUploadCommitted
          committedName={committedName}
          inputDisabled={inputDisabled}
          onReplace={() => archiveRef.current?.click()}
        />
      )}

      {pending && (
        <SourceUploadPending pending={pending} onConfirm={handleConfirm} onCancel={handleCancel} />
      )}

      {!committedName && !pending && (
        <SourceUploadDropzone
          dragging={dragging}
          inputDisabled={inputDisabled}
          onDragOver={(dragEvent) => {
            dragEvent.preventDefault();
            if (!inputDisabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !inputDisabled && archiveRef.current?.click()}
        />
      )}

      {disabledReason && (
        <div style={{ ...S_SOURCE_UPLOAD_STATUS_LINE_BASE, color: C.textMuted }}>
          {Ic.info(10)} {disabledReason}
        </div>
      )}

      {dropError && (
        <div style={{ ...S_SOURCE_UPLOAD_STATUS_LINE_BASE, color: "#b45309" }}>
          {Ic.info(10)} {dropError}
        </div>
      )}
    </div>
  );
}
