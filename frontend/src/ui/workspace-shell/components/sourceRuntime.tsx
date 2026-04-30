import type React from "react";
import { useRef, useState } from "react";
import { FIELD_META } from "../../../application/workspace-shell/fieldMeta";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { SourceUploadCommit } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { Ic } from "../../shared/components/Icon";
import { triggerOnEnterOrSpace } from "../../shared/keyboard";
import {
  C,
  F,
  hoverBorderColor,
  hoverBrightness,
  hoverColor,
  hoverIf,
  S_FIELD_ROW_BASE,
  S_FIELD_ROW_CONTENT,
  S_FIELD_ROW_DESC,
  S_FIELD_ROW_HEAD,
  S_FIELD_ROW_LABEL_BASE,
  S_RUNTIME_HELP_TEXT,
  S_RUNTIME_PICKER_WRAP,
  S_SOURCE_UPLOAD_STATUS_LINE_BASE,
  S_SOURCE_URL_STATUS_BASE,
} from "../../theme/theme";
import { FilePicker } from "./scriptAndFile";

const inp = (locked: boolean, extra: React.CSSProperties = {}): React.CSSProperties => ({
  width: "100%",
  border: `1.5px solid ${C.border}`,
  borderRadius: 7,
  padding: "9px 12px",
  fontSize: 14,
  fontFamily: F.mono,
  color: C.text,
  background: locked ? C.surfaceAlt : C.surface,
  transition: "border-color 0.15s, box-shadow 0.15s",
  ...extra,
});

function tipTargetChip(active: boolean, idleLabel = "Click for tips"): React.ReactNode {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: F.sans,
        color: active ? C.accent : C.textMuted,
        background: active ? C.accentBg : C.surfaceAlt,
        border: `1px solid ${active ? C.accentBorder : C.border}`,
        borderRadius: 99,
        padding: "1px 7px",
        letterSpacing: 0.2,
      }}
    >
      {Ic.info(10)} {active ? "Tips open" : idleLabel}
    </span>
  );
}

interface SourceUrlFieldProps {
  locked: boolean;
  committedValue: string;
  onCommit: (value: string) => void;
  onFocus?: () => void;
}
export function SourceUrlField({ locked, committedValue, onCommit, onFocus }: SourceUrlFieldProps) {
  const [draft, setDraft] = useState(committedValue || "");
  const [checkState, setCheckState] = useState<"idle" | "checking" | "reachable" | "unreachable">(
    "idle",
  );
  const [checkedFor, setCheckedFor] = useState<string>("");

  const prevCommitted = useRef<string | undefined>(committedValue);
  if (prevCommitted.current !== committedValue) {
    prevCommitted.current = committedValue;
    setDraft(committedValue || "");
    if ((committedValue || "") !== checkedFor) {
      setCheckState("idle");
      setCheckedFor("");
    }
  }

  const isDirty = draft.trim() !== (committedValue || "").trim();

  const handleCheckReachable = async () => {
    const candidate = draft.trim();
    if (!candidate) return;
    setCheckState("checking");
    setCheckedFor(candidate);
    await new Promise((resolve) => setTimeout(resolve, 700));
    const reachable = /^https?:\/\/[^\s]+$/i.test(candidate);
    setCheckState(reachable ? "reachable" : "unreachable");
    if (reachable) onCommit(candidate);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "stretch",
        }}
      >
        <div
          style={{
            flex: 1,
            position: "relative",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 10,
              top: "50%",
              transform: "translateY(-50%)",
              color: C.textMuted,
              pointerEvents: "none",
            }}
          >
            {Ic.link()}
          </div>
          <input
            disabled={locked}
            value={draft}
            onChange={(event) => {
              const next = event.target.value;
              setDraft(next);
              if (!next.trim()) {
                onCommit("");
              }
              if (checkedFor && next.trim() !== checkedFor) {
                setCheckState("idle");
                setCheckedFor("");
              }
            }}
            onFocus={onFocus}
            onKeyDown={(event) => {
              if (event.key === "Enter" && draft.trim()) handleCheckReachable();
            }}
            placeholder="https://github.com/org/repo"
            style={{
              ...inp(locked),
              paddingLeft: 32,
              borderColor: isDirty ? "#f59e0b" : undefined,
            }}
          />
        </div>
        <button
          type="button"
          onClick={handleCheckReachable}
          disabled={locked || !draft.trim() || checkState === "checking"}
          style={{
            ...{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 13px",
              borderRadius: 7,
              fontSize: 13,
              fontWeight: 600,
              fontFamily: F.sans,
              flexShrink: 0,
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            },
            cursor: locked || !draft.trim() || checkState === "checking" ? "default" : "pointer",
            border: `1.5px solid ${draft.trim() ? C.accentBorder : C.border}`,
            background: draft.trim() ? C.accentBg : C.surfaceAlt,
            color: draft.trim() ? C.accent : C.textMuted,
            opacity: locked ? 0.5 : 1,
          }}
          {...hoverIf(!locked && !!draft.trim() && checkState !== "checking", hoverBrightness(96))}
        >
          {checkState === "checking" ? Ic.loader(13) : Ic.link(13)} Check reachable
        </button>
      </div>
      {isDirty && draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#92400e" }}>
          {Ic.info(10)} Setting a new source will reset all downstream results.
        </div>
      )}
      {committedValue && !isDirty && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            fontSize: 11,
            fontFamily: F.mono,
            color: "#16a34a",
          }}
        >
          {Ic.check(10)}
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {committedValue}
          </span>
        </div>
      )}
      {checkState === "reachable" && checkedFor === draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#15803d" }}>
          {Ic.check(10)} URL reachable
        </div>
      )}
      {checkState === "unreachable" && checkedFor === draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#b45309" }}>
          {Ic.info(10)} URL not reachable (or invalid format)
        </div>
      )}
    </div>
  );
}

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
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 14px",
            borderRadius: 8,
            background: "#f0fdf4",
            border: "1.5px solid #bbf7d0",
            marginBottom: 8,
          }}
        >
          <span
            style={{
              color: "#16a34a",
              display: "flex",
            }}
          >
            {Ic.archive()}
          </span>
          <span
            style={{
              flex: 1,
              fontSize: 13,
              fontFamily: F.mono,
              color: "#15803d",
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {committedName}
          </span>
          {!inputDisabled && (
            <button
              type="button"
              onClick={() => archiveRef.current?.click()}
              disabled={inputDisabled}
              style={{
                background: "none",
                border: `1px solid ${C.border}`,
                borderRadius: 5,
                cursor: "pointer",
                color: C.textMuted,
                fontSize: 11,
                fontFamily: F.sans,
                padding: "2px 8px",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
              {...hoverBorderColor(C.accent, C.border)}
              {...hoverColor(C.accent, C.textMuted)}
            >
              {Ic.upload(11)} Replace
            </button>
          )}
        </div>
      )}

      {pending && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 5,
            marginBottom: 8,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 14px",
              borderRadius: 8,
              background: "#fffbeb",
              border: "1.5px solid #f59e0b",
            }}
          >
            <span
              style={{
                color: "#d97706",
                display: "flex",
              }}
            >
              {Ic.archive()}
            </span>
            <span
              style={{
                flex: 1,
                fontSize: 13,
                fontFamily: F.mono,
                color: "#92400e",
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {pending.archiveName}
            </span>
            <button
              type="button"
              onClick={handleConfirm}
              style={{
                background: "#fffbeb",
                border: "1.5px solid #f59e0b",
                borderRadius: 6,
                cursor: "pointer",
                color: "#b45309",
                fontSize: 12,
                fontWeight: 700,
                fontFamily: F.sans,
                padding: "4px 10px",
                display: "flex",
                alignItems: "center",
                gap: 4,
                flexShrink: 0,
              }}
              {...hoverBrightness(96)}
            >
              {Ic.check(11)} Add to workspace
            </button>
            <button
              type="button"
              onClick={handleCancel}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.textMuted,
                display: "flex",
                padding: 2,
                borderRadius: 4,
              }}
              {...hoverColor("#dc2626", C.textMuted)}
            >
              {Ic.x(13)}
            </button>
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#92400e",
              fontFamily: F.sans,
              display: "flex",
              alignItems: "center",
              gap: 4,
              paddingLeft: 2,
            }}
          >
            {Ic.info(10)} Setting a new source will reset all downstream results.
          </div>
        </div>
      )}

      {!committedName && !pending && (
        <button
          type="button"
          onDragOver={(dragEvent) => {
            dragEvent.preventDefault();
            if (!inputDisabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !inputDisabled && archiveRef.current?.click()}
          disabled={inputDisabled}
          style={{
            ...{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "22px 16px",
              borderRadius: 8,
              transition: "all 0.15s",
              width: "100%",
              appearance: "none",
            },
            cursor: inputDisabled ? "default" : "pointer",
            border: `1.5px dashed ${dragging ? C.accent : C.borderMid}`,
            background: dragging ? C.accentBg : C.bg,
            opacity: inputDisabled ? 0.55 : 1,
          }}
          onMouseEnter={(mouseEvent) => {
            if (!inputDisabled) {
              mouseEvent.currentTarget.style.borderColor = C.accent;
              mouseEvent.currentTarget.style.background = C.accentBg;
            }
          }}
          onMouseLeave={(mouseEvent) => {
            if (!dragging) {
              mouseEvent.currentTarget.style.borderColor = C.borderMid;
              mouseEvent.currentTarget.style.background = C.bg;
            }
          }}
        >
          <span
            style={{
              ...{
                display: "flex",
              },
              color: dragging ? C.accent : C.textMuted,
            }}
          >
            {Ic.upload(18)}
          </span>
          <span
            style={{
              ...{
                fontSize: 13,
                fontFamily: F.sans,
              },
              color: dragging ? C.accent : C.textMid,
            }}
          >
            Drop archive or{" "}
            <span
              style={{
                color: C.accent,
                fontWeight: 600,
              }}
            >
              browse archive
            </span>
          </span>
          <span
            style={{
              fontSize: 11,
              color: C.textMuted,
              fontFamily: F.mono,
              marginTop: 4,
            }}
          >
            .zip · .tar · .tar.gz
          </span>
        </button>
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

interface RuntimeFieldProps {
  locked: boolean;
  ree: Ree;
  onChange: (ree: Ree) => void;
  onFocus?: () => void;
  active?: boolean;
  files: FileTreeNode[];
}
export function RuntimeField({ locked, ree, onChange, onFocus, active, files }: RuntimeFieldProps) {
  const val = ree.runtime || "";
  const isSkipped = val === "__skipped__";
  const isTarball = !isSkipped && /\.(tar\.gz|tgz)$/i.test(val);
  const isImageRef = !isSkipped && !!val && !isTarball;
  const mode = isSkipped ? "skip" : isImageRef ? "image" : "tarball";

  const set = <K extends keyof Ree>(k: K, v: Ree[K]) => onChange({ ...ree, [k]: v } as Ree);

  const handleModeChange = (m: "tarball" | "image" | "skip") => {
    if (locked) return;
    if (m === "tarball") set("runtime", "");
    if (m === "image") set("runtime", isImageRef ? val : "");
    if (m === "skip") set("runtime", "__skipped__");
  };

  const meta = FIELD_META.runtime;

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: section container intentionally acts as full-surface tip target.
    <div
      id="field-runtime"
      onClick={onFocus ? () => onFocus?.() : undefined}
      role={onFocus ? "button" : undefined}
      tabIndex={onFocus ? 0 : undefined}
      onKeyDown={(event) => {
        if (!onFocus) return;
        triggerOnEnterOrSpace(event, () => onFocus?.());
      }}
      style={{
        ...S_FIELD_ROW_BASE,
        background: active ? `${C.accentBg}75` : "transparent",
        cursor: onFocus ? "pointer" : "default",
        borderLeftColor: active ? C.accent : "transparent",
        boxShadow: active ? `inset 0 0 0 1px ${C.accentBorder}` : "none",
      }}
    >
      <div>
        <div style={S_FIELD_ROW_HEAD}>
          <span
            style={{
              ...S_FIELD_ROW_LABEL_BASE,
              color: active ? C.accent : C.text,
            }}
          >
            {meta.label}
          </span>
          {!!onFocus && tipTargetChip(!!active)}
        </div>
        <p style={S_FIELD_ROW_DESC}>{meta.desc}</p>
      </div>

      <div
        style={{
          ...S_FIELD_ROW_CONTENT,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 5,
          }}
        >
          {(
            [
              { id: "tarball", label: "Tarball", icon: Ic.archive },
              { id: "image", label: "Image ref", icon: Ic.cpu },
            ] as const
          ).map((opt) => {
            const isActive = mode === opt.id || (mode === "skip" && opt.id === "tarball");
            return (
              <button
                type="button"
                key={opt.id}
                onClick={() => handleModeChange(opt.id)}
                disabled={locked}
                style={{
                  ...{
                    flex: 1,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 5,
                    padding: "6px 8px",
                    borderRadius: 7,
                    fontSize: 11,
                    fontWeight: 600,
                    fontFamily: F.sans,
                    transition: "all 0.15s",
                  },
                  cursor: locked ? "default" : "pointer",
                  border: `1.5px solid ${isActive ? C.accent : C.border}`,
                  background: isActive ? C.accentBg : C.surface,
                  color: isActive ? C.accent : C.textMid,
                  opacity: locked ? 0.6 : 1,
                }}
                {...hoverIf(!locked && !isActive, hoverBorderColor(C.borderMid, C.border))}
              >
                <span
                  style={{
                    display: "flex",
                  }}
                >
                  {opt.icon(11)}
                </span>
                {opt.label}
              </button>
            );
          })}
        </div>

        {(mode === "tarball" || mode === "skip") && (
          <div style={S_RUNTIME_PICKER_WRAP}>
            <FilePicker
              disabled={locked}
              value={isTarball ? val : ""}
              onChange={(v) => set("runtime", v)}
              files={files}
              placeholder="runtime.tar.gz"
              onFocus={onFocus}
              filterFn={(p) => /\.(tar\.gz|tgz)$/i.test(p)}
            />
            <div style={S_RUNTIME_HELP_TEXT}>
              Bundled into the REE archive on deposit. Produced by your build script via{" "}
              <code
                style={{
                  fontFamily: F.mono,
                  fontSize: 10.5,
                  background: C.surfaceAlt,
                  padding: "1px 4px",
                  borderRadius: 3,
                }}
              >
                docker save … | gzip
              </code>
              .
            </div>
            {isSkipped && (
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  padding: "8px 11px",
                  background: "#fff7ed",
                  border: "1px solid #fde68a",
                  borderRadius: 7,
                }}
              >
                <span
                  style={{
                    color: "#d97706",
                    display: "flex",
                    flexShrink: 0,
                    marginTop: 1,
                  }}
                >
                  {Ic.info(12)}
                </span>
                <div
                  style={{
                    fontSize: 11,
                    color: "#92400e",
                    lineHeight: 1.5,
                  }}
                >
                  Tarball will <strong>not</strong> be bundled in the REE archive. Ensure it is
                  reproducible from the build script alone.
                </div>
              </div>
            )}
          </div>
        )}

        {mode === "image" && (
          <div style={S_RUNTIME_PICKER_WRAP}>
            <input
              disabled={locked}
              value={isImageRef ? val : ""}
              onChange={(event) => set("runtime", event.target.value)}
              onFocus={onFocus}
              placeholder="ree:latest  or  sha256:abc123…"
              style={inp(locked)}
            />
            <div style={S_RUNTIME_HELP_TEXT}>
              A Docker/Podman image name or digest. Not bundled in the REE — the image must be
              rebuilt from the build script. Used by the SBOM step as the syft scan target.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
