import { useRef, useState } from "react";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import { fileType } from "../../../shared/formatting";
import { C } from "../../../theme/theme";
import { allFilePaths, findFileByPath } from "../../pages/sharedAssemblyHelpers";
import { FilePickerPreview, FilePickerWarning } from "./FilePickerPreviewSections";
import { FilePickerDropdown, FilePickerInputRow } from "./FilePickerSections";
import { FILE_TYPE_COLORS, PREVIEW_LINES } from "./shared";

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
        <FilePickerInputRow
          draft={draft}
          disabled={disabled}
          placeholder={placeholder}
          onFocus={onFocus}
          open={open}
          previewOpen={previewOpen}
          isValid={isValid}
          notFound={notFound}
          wrongFormat={!!wrongFormat}
          typeStyle={typeStyle}
          borderColor={borderColor}
          onDraftChange={handleDraftChange}
          onToggleOpen={() => setOpen((current) => !current)}
          onTogglePreview={() => setPreviewOpen((current) => !current)}
        />

        <FilePickerDropdown
          open={open}
          paths={paths}
          filterFn={filterFn}
          draft={draft}
          onSelect={handleSelect}
        />
      </div>

      <FilePickerWarning
        notFound={notFound}
        wrongFormat={!!wrongFormat}
        placeholder={placeholder}
      />

      <FilePickerPreview
        isValid={isValid}
        previewOpen={previewOpen}
        matchedFile={matchedFile}
        trimmedDraft={trimmedDraft}
        typeStyle={typeStyle}
        previewLines={previewLines}
        fileLineCount={fileLineCount}
        onClose={() => setPreviewOpen(false)}
      />
    </div>
  );
}
