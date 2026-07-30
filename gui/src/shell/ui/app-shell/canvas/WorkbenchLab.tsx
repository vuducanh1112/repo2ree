import { APP_ROUTE, LOAD_REE_PARAM } from "@core/app-shell/pages";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import { appendLine } from "@core/ree/logEntry";
import type { LogEntry, LogLine } from "@core/ree/ReeTypes";
import { runFailurePresentation } from "@core/runs/runFailurePresentation";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useAgents } from "@shell/data/agents/agents";
import { useReeRunsClient } from "@shell/data/runs/client";
import { observeReeRun } from "@shell/data/runs/queries";
import { useWorkbenchImageCatalog } from "@shell/data/workbench/images";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Ic } from "../../shared/components/Icon";
import { lgColors, lgInfoBanner, lgPrimaryActionButton } from "../../theme/lightGlassTheme";
import { C, F } from "../../theme/theme";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import {
  DEFAULT_WORKBENCH_IMAGE_SELECTION,
  resolveWorkbenchImage,
  WORKBENCH_COLOR,
  type WorkbenchImageSelection,
  WorkbenchImageSelector,
} from "../pages/workbench/WorkbenchPageSections";
import { PodWidget } from "./PodWidget";

interface WorkbenchLabProps {
  evaluation: EvaluationState;
}

// The first screen of REE creation. The workbench is not a panel cabled to the
// pod — it IS the lab the pod sits in, so the whole canvas is the bench: a
// dormant specimen seated in its cradle, waiting for the bench console (right)
// to power the lab on. Provisioning flips `provisioned` upstream, which swaps
// this view for the live CanvasHub.
export function WorkbenchLab({ evaluation }: WorkbenchLabProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const runsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const { data: imageCatalog } = useWorkbenchImageCatalog();
  const { data: agents } = useAgents();
  const images = imageCatalog?.images ?? [];
  const defaultImageId = imageCatalog?.defaultId ?? "";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry | null>(null);
  const [imageSelection, setImageSelection] = useState<WorkbenchImageSelection>(
    DEFAULT_WORKBENCH_IMAGE_SELECTION,
  );
  // An REE can be started blank or loaded from a downloaded bundle. The bundle
  // is picked here rather than on the landing screen because the load runs on
  // the workbench this step provisions.
  const [bundle, setBundle] = useState<File | null>(null);

  // The lab location (agent) was chosen on the previous step and carried here as
  // ?agentId=…. Empty means "any available agent" (single-agent setups).
  const agentId = searchParams.get("agentId") ?? "";
  // Arrived from "Load REE" on the landing screen: this workbench exists to
  // host an existing REE, so it will not provision until one is chosen.
  const loadRequested = Boolean(searchParams.get(LOAD_REE_PARAM));
  const selectedAgent = agents?.find((a) => a.id === agentId);
  const provisionLabel = selectedAgent?.hostname || (agentId ? agentId : "any available agent");

  async function handleProvision() {
    const image = resolveWorkbenchImage(imageSelection, images);
    setLoading(true);
    setError(null);
    const startedTs = appShellPorts.clock.nowIso();
    // Preamble lines we own locally; the run's streamed log lines are appended
    // after these on every poll update.
    const preamble: LogLine[] = [
      { type: "info", msg: "Powering up the workbench…", ts: startedTs },
      { type: "out", msg: `Image: ${image ?? "server default"}`, ts: startedTs },
      { type: "out", msg: `Location: ${provisionLabel}`, ts: startedTs },
    ];
    setLog({ lines: preamble, ts: startedTs });
    try {
      // The REE's display name is owned by the Metadata page; provision with a
      // neutral default and let the user rename it there. Provisioning runs in
      // the background so the image pull streams live — observeReeRun
      // tails the run's log feed into the bench console until it finishes.
      const { reeId, run } = await runsClient.createWorkspace("REE", image, agentId);
      const result = await observeReeRun(queryClient, runsClient, {
        reeId,
        runId: run.runId,
        onUpdate: ({ lines, ts }) => setLog({ lines: [...preamble, ...lines], ts }),
      });
      if (result.status !== "succeeded") {
        // Prefer the typed failure reason over a bare status, so the user sees
        // *why* provisioning failed (e.g. "Workbench unavailable") rather than
        // just "failed".
        const reason = result.failure
          ? runFailurePresentation(result.failure).label
          : `Provisioning ${result.status}`;
        throw new Error(reason);
      }
      setLog((l) =>
        appendLine(l, "ok", "Lab online — seating the specimen", appShellPorts.clock.nowIso()),
      );
      if (bundle) {
        await loadBundleOnto(reeId, bundle);
      }
      navigate(`${APP_ROUTE.WORKSPACE}?reeId=${encodeURIComponent(reeId)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Provisioning failed";
      setError(msg);
      setLog((l) => appendLine(l, "err", msg, appShellPorts.clock.nowIso()));
    } finally {
      setLoading(false);
    }
  }

  // Restore a downloaded REE onto the workbench just provisioned. Its log feed
  // is tailed into the same console, appended after the provisioning lines the
  // user has been watching.
  async function loadBundleOnto(reeId: string, file: File) {
    setLog((l) =>
      appendLine(
        l,
        "info",
        `Loading ${file.name} onto the workbench…`,
        appShellPorts.clock.nowIso(),
      ),
    );
    const preamble = log?.lines ?? [];
    const run = await runsClient.loadReeBundle(reeId, file);
    const result = await observeReeRun(queryClient, runsClient, {
      reeId,
      runId: run.runId,
      onUpdate: ({ lines, ts }) => setLog({ lines: [...preamble, ...lines], ts }),
    });
    if (result.status !== "succeeded") {
      throw new Error(
        result.failure ? runFailurePresentation(result.failure).label : `Load ${result.status}`,
      );
    }
    setLog((l) => appendLine(l, "ok", "REE loaded — opening it", appShellPorts.clock.nowIso()));
  }

  return (
    <div style={benchSurface}>
      {/* bench tray frame — the lab the pod sits in */}
      <div style={benchTray} />

      <div style={labLayout}>
        <DormantSpecimen evaluation={evaluation} ready />

        <section style={consolePanel}>
          <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 4 }}>
            <span style={consoleIcon}>{Ic.package(20)}</span>
            <div>
              <h1
                style={{ fontSize: 17, fontWeight: 700, color: lgColors.text, letterSpacing: -0.3 }}
              >
                Set up the workbench
              </h1>
              <p style={{ fontSize: 12.5, color: lgColors.textMuted, marginTop: 1 }}>
                Configure the isolated lab that will host this REE.
              </p>
            </div>
          </div>

          <SectionLabel icon={Ic.cpu(14)}>Lab location</SectionLabel>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "12px 14px",
              borderRadius: 9,
              border: `1.5px solid ${C.border}`,
              background: C.surface,
            }}
          >
            <span
              style={{
                width: 34,
                height: 34,
                borderRadius: 9,
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: WORKBENCH_COLOR,
                background: C.accentBg,
                border: `1px solid ${C.accentBorder}`,
              }}
            >
              {Ic.cpu(16)}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: lgColors.text }}>
                {provisionLabel}
              </div>
              <div style={{ fontSize: 12, color: lgColors.textMuted, marginTop: 1 }}>
                {selectedAgent
                  ? `${selectedAgent.dockerMode} · ${selectedAgent.id}`
                  : "No specific agent selected"}
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate(APP_ROUTE.LAB_LOCATION)}
              style={{
                background: "transparent",
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "6px 10px",
                color: lgColors.textMid,
                fontSize: 12,
                cursor: "pointer",
                fontFamily: F.sans,
                flexShrink: 0,
              }}
            >
              Change
            </button>
          </div>

          <SectionLabel icon={Ic.layers(14)}>Image</SectionLabel>
          <WorkbenchImageSelector
            images={images}
            defaultId={defaultImageId}
            selection={imageSelection}
            onChange={setImageSelection}
            disabled={loading}
          />

          <SectionLabel icon={Ic.package(14)}>Contents</SectionLabel>
          <BundleChoice
            bundle={bundle}
            disabled={loading}
            required={loadRequested}
            onChange={setBundle}
          />

          {error && (
            <div style={lgInfoBanner("danger")}>
              <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.x(14)}</span>
              <span style={{ fontSize: 13, color: lgColors.danger }}>{error}</span>
            </div>
          )}

          {log && <CollapsibleLogCard log={log} running={loading} title="Provisioning log" />}

          <button
            type="button"
            onClick={handleProvision}
            disabled={loading || (loadRequested && !bundle)}
            style={{
              ...lgPrimaryActionButton(loading || (loadRequested && !bundle)),
              justifyContent: "center",
            }}
          >
            {loading ? Ic.loader(15) : Ic.package(15)}
            <span>
              {loading ? "Powering up…" : bundle ? "Provision and load REE" : "Provision workbench"}
            </span>
          </button>
          <span style={{ fontSize: 11.5, color: lgColors.textMuted, textAlign: "center" }}>
            Brings the lab online — this can take a moment on first run.
          </span>
        </section>
      </div>
    </div>
  );
}

// The pod, seated dormant in its cradle on the bench. It's de-energized
// (greyscale, dimmed) until the lab is provisioned — the visual promise that
// powering up the workbench brings the specimen to life.
function DormantSpecimen({ evaluation, ready }: { evaluation: EvaluationState; ready: boolean }) {
  return (
    <div style={cradleColumn}>
      <div style={{ position: "relative", width: 300, height: 300 }}>
        {/* cradle socket on the bench surface */}
        <div style={cradleDisc} />
        <div
          style={{
            ...cradleRing,
            animation: ready ? "cradlePulse 3.2s ease-in-out infinite" : "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            filter: "grayscale(0.85) brightness(1.04)",
            opacity: 0.62,
          }}
        >
          <PodWidget evaluation={evaluation} size={250} />
        </div>
      </div>
      <div style={{ textAlign: "center", marginTop: 6 }}>
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 10.5,
            letterSpacing: 1.4,
            textTransform: "uppercase",
            color: C.textMuted,
          }}
        >
          Specimen pod · dormant
        </div>
        <div
          style={{ fontSize: 12.5, color: C.textMid, marginTop: 5, maxWidth: 240, lineHeight: 1.5 }}
        >
          Provision the workbench to bring the lab online and seat the specimen.
        </div>
      </div>
    </div>
  );
}

// Blank vs. loaded: the REE either starts empty or *is* a downloaded bundle
// (sealed or draft) restored onto this workbench — intent, source, and the
// author's receipts, the baseline a review reproduces against.
function BundleChoice({
  bundle,
  disabled,
  required,
  onChange,
}: {
  bundle: File | null;
  disabled: boolean;
  required: boolean;
  onChange: (file: File | null) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "12px 14px",
        borderRadius: 9,
        border: `1.5px solid ${required && !bundle ? C.accentBorder : C.border}`,
        background: C.surface,
      }}
    >
      <div style={{ fontSize: 13, color: lgColors.textMid, lineHeight: 1.5 }}>
        {bundle
          ? "This workbench will be loaded with the uploaded REE."
          : required
            ? "Choose the downloaded REE bundle (.zip) to load onto this workbench."
            : "Start blank, or load a downloaded REE bundle (.zip) onto this workbench."}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
            padding: "6px 10px",
            background: "transparent",
            color: lgColors.textMid,
            fontSize: 12,
            fontFamily: F.sans,
            cursor: disabled ? "not-allowed" : "pointer",
            flexShrink: 0,
          }}
        >
          {Ic.upload(14)}
          <span>{bundle ? "Choose another" : "Choose REE bundle"}</span>
          <input
            type="file"
            accept=".zip,application/zip"
            disabled={disabled}
            aria-label="REE bundle"
            style={{ display: "none" }}
            onChange={(event) => onChange(event.target.files?.[0] ?? null)}
          />
        </label>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 12,
              fontFamily: F.mono,
              color: bundle ? lgColors.text : lgColors.textMuted,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {bundle
              ? bundle.name
              : required
                ? "No bundle selected yet"
                : "No bundle selected — blank REE"}
          </div>
        </div>
        {bundle && (
          <button
            type="button"
            onClick={() => onChange(null)}
            disabled={disabled}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              padding: "6px 10px",
              color: lgColors.textMid,
              fontSize: 12,
              fontFamily: F.sans,
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 6 }}>
      <span style={{ color: WORKBENCH_COLOR, display: "flex" }}>{icon}</span>
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: 0.8,
          textTransform: "uppercase",
          color: lgColors.textMid,
        }}
      >
        {children}
      </span>
    </div>
  );
}

const benchSurface: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  overflow: "auto",
  background: `
    radial-gradient(circle at 50% 42%, #ffffff 0%, ${C.bg} 62%),
    linear-gradient(${C.border} 1px, transparent 1px) 0 0 / 26px 26px,
    linear-gradient(90deg, ${C.border} 1px, transparent 1px) 0 0 / 26px 26px`,
};

// Inset frame that reads as the bench tray / lab walls around the surface.
const benchTray: React.CSSProperties = {
  position: "absolute",
  inset: 14,
  borderRadius: 18,
  border: `1px solid ${C.border}`,
  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.5), inset 0 18px 60px rgba(13,17,23,0.05)",
  pointerEvents: "none",
};

const labLayout: React.CSSProperties = {
  position: "relative",
  minHeight: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 48,
  flexWrap: "wrap",
  padding: "48px 56px",
};

const cradleColumn: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  flexShrink: 0,
};

const cradleDisc: React.CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "64%",
  width: 230,
  height: 78,
  transform: "translate(-50%,-50%)",
  borderRadius: "50%",
  background: "radial-gradient(ellipse at center, rgba(100,116,139,0.16) 0%, transparent 70%)",
};

const cradleRing: React.CSSProperties = {
  position: "absolute",
  left: "50%",
  top: "62%",
  width: 196,
  height: 60,
  transform: "translate(-50%,-50%)",
  borderRadius: "50%",
  border: `1.5px dashed ${C.borderMid}`,
};

const consolePanel: React.CSSProperties = {
  position: "relative",
  width: 408,
  maxWidth: "100%",
  flexShrink: 0,
  display: "flex",
  flexDirection: "column",
  gap: 13,
  background: C.surface,
  border: `1px solid ${C.border}`,
  borderRadius: 16,
  padding: 22,
  boxShadow: "0 18px 48px rgba(13,17,23,0.12)",
  animation: "fadeUp 0.4s ease",
};

const consoleIcon: React.CSSProperties = {
  width: 38,
  height: 38,
  borderRadius: 10,
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: C.accentBg,
  border: `1px solid ${C.accentBorder}`,
  color: WORKBENCH_COLOR,
};
