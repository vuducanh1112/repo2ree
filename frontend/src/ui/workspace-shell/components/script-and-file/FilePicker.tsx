import { useRef, useState } from "react";
import type { FileTreeNode } from "../../../../domain/workspace/FileTree";
import { Ic, Svg } from "../../../shared/components/Icon";
import { fileType } from "../../../shared/formatting";
import { C, F, hoverBg, hoverColor, hoverIf } from "../../../theme/theme";
import { allFilePaths, findFileByPath } from "../../pages/sharedWorkflowHelpers";
import { CodeLineList, FILE_TYPE_COLORS, PREVIEW_LINES } from "./shared";

interface FilePickerProps {
  value: string;
  onChange: (value: string) => void;
  files: FileTreeNode[];
  placeholder?: string;
  disabled?: boolean;
  onFocus?: () => void;
  filterFn?: (path: string) => boolean;
}

export function FilePicker({
  value,
  onChange,
  files,
  placeholder,
  disabled,
  onFocus,
  filterFn,
}: FilePickerProps) {
  const [open, setOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [draft, setDraft] = useState(value || "");

  const prevValue = useRef(value);
  if (prevValue.current !== value) {
    const previous = prevValue.current;
    prevValue.current = value;
    setDraft((current) => (current === previous ? value || "" : current));
  }

  const allPaths = allFilePaths(files);
  const paths = filterFn ? allPaths.filter(filterFn) : allPaths;

  const trimmedDraft = draft.trim();
  const matchedFile = trimmedDraft ? findFileByPath(files, trimmedDraft) : null;
  const notFound = trimmedDraft.length > 0 && !matchedFile;
  const wrongFormat = filterFn && trimmedDraft.length > 0 && !filterFn(trimmedDraft);
  const typeStyle = FILE_TYPE_COLORS[fileType(trimmedDraft)] || FILE_TYPE_COLORS.text;

  const previewLines = matchedFile
    ? (matchedFile.content || "").split("\n").slice(0, PREVIEW_LINES)
    : [];
  const fileLineCount = matchedFile ? (matchedFile.content || "").split("\n").length : 0;
  const hasMore = fileLineCount > PREVIEW_LINES;

  const isValid = matchedFile && !wrongFormat;
  const borderColor = notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.border;

  const handleDraftChange = (raw: string) => {
    setDraft(raw);
    setPreviewOpen(false);
    const trimmed = raw.trim();
    if (!trimmed) {
      onChange("");
      return;
    }
    const file = findFileByPath(files, trimmed);
    const passesFormat = !filterFn || filterFn(trimmed);
    onChange(file && passesFormat ? trimmed : "");
  };

  const handleSelect = (path: string) => {
    setDraft(path);
    setOpen(false);
    setPreviewOpen(true);
    onChange(path);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ position: "relative" }}>
        <div
          style={{
            display: "flex",
            overflow: "hidden",
            transition: "border-color 0.2s",
            border: `1.5px solid ${borderColor}`,
            borderRadius: isValid && previewOpen ? "7px 7px 0 0" : "7px",
            background: disabled ? C.surfaceAlt : C.surface,
            boxShadow: isValid
              ? `0 0 0 3px #22c55e10`
              : notFound || wrongFormat
                ? `0 0 0 3px #f9731610`
                : "none",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 8px 0 10px",
              flexShrink: 0,
              transition: "color 0.2s",
              color: notFound || wrongFormat ? "#f97316" : isValid ? "#22c55e" : C.textMuted,
            }}
          >
            {notFound || wrongFormat ? (
              <Svg
                size={14}
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              />
            ) : isValid ? (
              Ic.check(14)
            ) : (
              Ic.file(14)
            )}
          </div>

          <input
            value={draft}
            onChange={(event) => handleDraftChange(event.target.value)}
            disabled={disabled}
            placeholder={placeholder || "path/to/file"}
            onFocus={onFocus}
            style={{
              flex: 1,
              border: "none",
              padding: "7px 4px 7px 0",
              fontSize: 14,
              fontFamily: F.mono,
              color: C.text,
              background: "transparent",
            }}
          />

          {isValid && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "0 8px",
                flexShrink: 0,
                borderLeft: `1px solid ${typeStyle.border}`,
                background: typeStyle.bg,
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  letterSpacing: 0.5,
                  textTransform: "uppercase",
                  color: typeStyle.color,
                }}
              >
                {typeStyle.label}
              </span>
            </div>
          )}

          {isValid && !disabled && (
            <button
              type="button"
              onClick={() => setPreviewOpen((current) => !current)}
              title={previewOpen ? "Hide preview" : "Peek at file contents"}
              style={{
                border: "none",
                padding: "7px 9px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                fontFamily: F.sans,
                fontWeight: 600,
                transition: "background 0.15s, color 0.15s",
                flexShrink: 0,
                background: previewOpen ? "#f0fdf4" : C.surfaceAlt,
                borderLeft: `1px solid ${previewOpen ? "#bbf7d0" : C.border}`,
                color: previewOpen ? "#16a34a" : C.textMid,
              }}
              {...hoverIf(!previewOpen, hoverBg(C.accentBg, C.surfaceAlt))}
              {...hoverIf(!previewOpen, hoverColor(C.accent, C.textMid))}
            >
              {Ic.terminal(13)}
              <span style={{ display: "none" }}>{previewOpen ? "hide" : "peek"}</span>
            </button>
          )}

          {!disabled && (
            <button
              type="button"
              onClick={() => setOpen((current) => !current)}
              title="Browse repository files"
              style={{
                border: "none",
                padding: "7px 9px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                transition: "background 0.15s, color 0.15s",
                background: open ? C.accentBg : C.surfaceAlt,
                borderLeft: `1px solid ${C.border}`,
                color: open ? C.accent : C.textMid,
              }}
              {...hoverIf(!open, hoverBg(C.accentBg, C.surfaceAlt))}
              {...hoverIf(!open, hoverColor(C.accent, C.textMid))}
            >
              {Ic.folder()}
            </button>
          )}
        </div>

        {open && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              zIndex: 50,
              background: C.surface,
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
              maxHeight: 180,
              overflowY: "auto",
            }}
          >
            {paths.length === 0 ? (
              <div
                style={{
                  padding: "12px",
                  fontSize: 13,
                  color: C.textMuted,
                  fontFamily: F.sans,
                  textAlign: "center",
                }}
              >
                {filterFn ? "No matching files in repository" : "No files in repository"}
              </div>
            ) : (
              paths.map((path) => (
                <button
                  type="button"
                  key={path}
                  onClick={() => handleSelect(path)}
                  style={{
                    padding: "7px 12px",
                    fontSize: 13,
                    fontFamily: F.mono,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    border: "none",
                    textAlign: "left",
                    width: "100%",
                    background: draft === path ? C.accentBg : "transparent",
                    color: draft === path ? C.accent : C.textMid,
                  }}
                  {...hoverIf(draft !== path, hoverBg(C.surfaceAlt, "transparent"))}
                >
                  <span style={{ display: "flex", opacity: 0.5 }}>{Ic.file(12)}</span>
                  {path}
                </button>
              ))
            )}
          </div>
        )}
      </div>

      {(notFound || wrongFormat) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "5px 10px",
            background: "#fff7ed",
            border: "1px solid #fed7aa",
            borderTop: "none",
            borderRadius: "0 0 6px 6px",
            animation: "fadeUp 0.15s ease",
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: "#c2410c",
              fontFamily: F.sans,
            }}
          >
            {wrongFormat && notFound
              ? `Wrong format — expected ${placeholder || "the required format"}. File not found either.`
              : wrongFormat
                ? `Wrong format — this field only accepts ${placeholder || "the required format"}. Field not saved.`
                : "File not found in repository — field not saved until the path resolves."}
          </span>
        </div>
      )}

      {isValid && previewOpen && matchedFile && (
        <div
          style={{
            border: "1.5px solid #22c55e",
            borderTop: "none",
            borderRadius: "0 0 7px 7px",
            background: C.surfaceAlt,
            overflow: "hidden",
            animation: "fadeUp 0.15s ease",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "5px 12px",
              borderBottom: `1px solid ${C.border}`,
              background: C.surface,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ display: "flex", color: "#16a34a", opacity: 0.9 }}>{Ic.file(12)}</span>
              <span
                style={{
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: C.textMid,
                  letterSpacing: 0.3,
                }}
              >
                {trimmedDraft}
              </span>
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  letterSpacing: 0.8,
                  textTransform: "uppercase",
                  padding: "1px 5px",
                  borderRadius: 3,
                  background: typeStyle.bg,
                  color: typeStyle.color,
                  border: `1px solid ${typeStyle.border}`,
                }}
              >
                {typeStyle.label}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setPreviewOpen(false)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: C.textMuted,
                display: "flex",
                padding: "2px",
                borderRadius: 3,
              }}
              {...hoverColor(C.textMid, C.textMuted)}
            >
              {Ic.x(12)}
            </button>
          </div>

          <div style={{ padding: "8px 0 6px" }}>
            <CodeLineList lines={previewLines} paddingRight={14} />
            {hasMore && (
              <div
                style={{
                  padding: "4px 12px 2px 36px",
                  fontSize: 11,
                  fontFamily: F.mono,
                  color: C.textMuted,
                  fontStyle: "italic",
                }}
              >
                … {fileLineCount - PREVIEW_LINES} more lines
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
