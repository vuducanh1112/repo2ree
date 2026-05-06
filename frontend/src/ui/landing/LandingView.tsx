import type React from "react";
import { useRef, useState } from "react";
import { APP_ROUTE, type AppLoadRoutePath } from "../../application/state/pages";
import { LEVELS } from "../../core/review/levels";
import { useApiRuntime } from "../../data/apiRuntime";
import { useReeClient } from "../../data/ree/client";
import { useReviewClient } from "../../data/reviews/client";
import { Ic } from "../shared/components/Icon";
import { C, F, hoverBg, hoverColor, S_ACTION_BUTTON_BASE, S_SECTION_LABEL } from "../theme/theme";

interface LandingViewProps {
  onLoad: (path: AppLoadRoutePath) => void;
}

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

export function LandingView({ onLoad }: LandingViewProps) {
  const { reeId } = useApiRuntime();
  const reviewClient = useReviewClient();
  const reeClient = useReeClient();
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [loadingReviewUpload, setLoadingReviewUpload] = useState(false);
  const [reviewError, setReviewError] = useState<string>("");
  const reviewZipInputRef = useRef<HTMLInputElement | null>(null);

  const createRee = async () => {
    setLoadingCreate(true);
    try {
      const ree = await reeClient.getRee(reeId);
      onLoad(`${APP_ROUTE.WORKSPACE}?reeId=${encodeURIComponent(ree.id)}`);
    } catch {
      onLoad(APP_ROUTE.WORKSPACE);
    } finally {
      setLoadingCreate(false);
    }
  };

  const startReviewFromZip = async (file: File) => {
    setLoadingReviewUpload(true);
    setReviewError("");
    try {
      const init = await reviewClient.initReviewUpload({
        fileName: file.name,
        size: file.size,
        contentType: file.type || "application/zip",
      });

      await reviewClient.uploadReviewBytes(init.uploadUrl, await file.arrayBuffer());
      await reviewClient.completeReviewUpload(init.reviewId, {
        uploadToken: init.uploadToken,
        archiveName: file.name,
      });

      onLoad(`${APP_ROUTE.REVIEWER}?reviewId=${encodeURIComponent(init.reviewId)}`);
    } catch (error) {
      setReviewError(
        error instanceof Error
          ? error.message
          : "Failed to start review. Upload a ZIP containing ree/ree.json.",
      );
    } finally {
      setLoadingReviewUpload(false);
    }
  };

  const handleReviewZipSelection: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const selectedFile = event.target.files?.[0];
    event.currentTarget.value = "";
    if (!selectedFile) {
      return;
    }
    if (!selectedFile.name.toLowerCase().endsWith(".zip")) {
      setReviewError("Review upload requires a .zip archive containing ree/ree.json.");
      return;
    }
    void startReviewFromZip(selectedFile);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 430, width: "100%", animation: "fadeUp 0.4s ease" }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 50,
              height: 50,
              borderRadius: 13,
              background: C.accentBg,
              border: `1px solid ${C.accentBorder}`,
              color: C.accent,
              marginBottom: 14,
            }}
          >
            {Ic.layers(22)}
          </div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 600,
              color: C.text,
              letterSpacing: -0.5,
              marginBottom: 6,
            }}
          >
            REE Workspace
          </h1>
          <p style={{ fontSize: 14, color: C.textMid, lineHeight: 1.6 }}>
            Build, inspect, and certify
            <br />
            Reproducible Execution Environments
          </p>
        </div>
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 14,
            padding: 22,
            boxShadow: "0 2px 12px rgba(0,0,0,0.05)",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div
            style={{
              ...S_SECTION_LABEL,
              letterSpacing: 1.4,
            }}
          >
            Choose Action
          </div>
          <button
            type="button"
            onClick={() => {
              void createRee();
            }}
            disabled={loadingCreate}
            style={{
              ...actionBtn({
                border: "none",
                borderRadius: 8,
                padding: "10px 16px",
                fontSize: 14,
                fontWeight: 600,
                background: C.accent,
                color: "#fff",
                transition: "all 0.12s",
              }),
              borderRadius: 10,
              background: C.accent,
              color: "#fff",
              cursor: "pointer",
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 5,
              justifyContent: "center",
            }}
          >
            <span
              style={{
                display: "flex",
                animation: loadingCreate ? "spin 0.9s linear infinite" : "none",
              }}
            >
              {loadingCreate ? Ic.loader() : Ic.play()}
            </span>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              {loadingCreate ? "Creating…" : "Create REE"}
            </span>
          </button>
          <button
            type="button"
            onClick={() => reviewZipInputRef.current?.click()}
            disabled={loadingCreate || loadingReviewUpload}
            style={{
              ...actionBtn({
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: 8,
                background: "transparent",
                color: C.textMid,
                fontWeight: 400,
                transition: "background 0.13s, color 0.13s",
              }),
              background: "transparent",
              cursor: "pointer",
              width: "100%",
              color: C.textMid,
            }}
            {...hoverBg(C.surfaceAlt, "transparent")}
            {...hoverColor(C.text, C.textMid)}
          >
            {loadingReviewUpload ? "Uploading Review ZIP…" : "Review REE"}
          </button>
          <input
            ref={reviewZipInputRef}
            type="file"
            accept=".zip,application/zip"
            onChange={handleReviewZipSelection}
            style={{ display: "none" }}
          />
          {reviewError && (
            <div style={{ fontSize: 12, color: "#b91c1c", lineHeight: 1.4 }}>{reviewError}</div>
          )}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 12,
            marginTop: 20,
            flexWrap: "wrap",
          }}
        >
          {LEVELS.map((l) => (
            <div
              key={l.n}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                fontSize: 11,
                color: C.textMuted,
                fontFamily: F.sans,
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: l.color }} />L
              {l.n} {l.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
