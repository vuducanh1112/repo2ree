import { FIELD_META } from "../../../../application/state/fieldMeta";
import type { ReeViewState } from "../../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { triggerOnEnterOrSpace } from "../../../shared/keyboard";
import {
  C,
  F,
  hoverBorderColor,
  hoverIf,
  S_FIELD_ROW_BASE,
  S_FIELD_ROW_CONTENT,
  S_FIELD_ROW_DESC,
  S_FIELD_ROW_HEAD,
  S_FIELD_ROW_LABEL_BASE,
  S_RUNTIME_HELP_TEXT,
  S_RUNTIME_PICKER_WRAP,
} from "../../../theme/theme";
import { FilePicker } from "../scriptAndFile";
import { inp, tipTargetChip } from "./shared";

interface RuntimeFieldProps {
  locked: boolean;
  ree: ReeViewState;
  onChange: (ree: ReeViewState) => void;
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

  const set = <K extends keyof ReeViewState>(k: K, v: ReeViewState[K]) =>
    onChange({ ...ree, [k]: v } as ReeViewState);

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
