import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { EvaluationState } from "../../../../core/evaluate/EvaluationState";
import { appendLine } from "../../../../core/ree/logEntry";
import type { LogEntry } from "../../../../core/ree/ReeTypes";
import { useApiRuntime } from "../../../data/apiRuntime";
import { Ic } from "../../shared/components/Icon";
import {
  lgColors,
  lgContentCard,
  lgInfoBanner,
  lgInput,
  lgPrimaryActionButton,
  lgStyles,
} from "../../theme/lightGlassTheme";
import { C, F } from "../../theme/theme";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import { PodWidget } from "../pages/overview/PodWidget";
import {
  ImageCard,
  LocationOption,
  STANDARD_IMAGE,
  WORKBENCH_COLOR,
} from "../pages/workbench/WorkbenchPageSections";
import { APP_ROUTE } from "../state/pages";

type LocationType = "local" | "remote";

interface SshDetails {
  host: string;
  user: string;
  port: string;
}

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
  const { reeApi } = useApiRuntime();
  const [location, setLocation] = useState<LocationType>("local");
  const [ssh, setSsh] = useState<SshDetails>({ host: "", user: "", port: "22" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry | null>(null);

  const provisionLabel = location === "remote" && ssh.host ? ssh.host : "this machine";
  const canProvision = location === "local" || ssh.host.trim().length > 0;

  async function handleProvision() {
    setLoading(true);
    setError(null);
    setLog(appendLine(null, "info", "Powering up the workbench…"));
    setLog((l) => appendLine(l, "out", `Image: ${STANDARD_IMAGE.ref}`));
    setLog((l) => appendLine(l, "out", `Location: ${provisionLabel}`));
    try {
      // The REE's display name is owned by the Metadata page; provision with a
      // neutral default and let the user rename it there.
      const created = await reeApi.createRee({ sourceMode: "upload", name: "REE" });
      setLog((l) => appendLine(l, "ok", "Lab online — seating the specimen"));
      navigate(`${APP_ROUTE.WORKSPACE}?reeId=${encodeURIComponent(created.reeId)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Provisioning failed";
      setError(msg);
      setLog((l) => appendLine(l, "err", msg));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={benchSurface}>
      {/* bench tray frame — the lab the pod sits in */}
      <div style={benchTray} />

      <div style={labLayout}>
        <DormantSpecimen evaluation={evaluation} ready={canProvision} />

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

          <SectionLabel icon={Ic.cpu(14)}>Location</SectionLabel>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <LocationOption
              selected={location === "local"}
              icon={Ic.cpu(16)}
              label="Local"
              description="Run on this machine"
              onSelect={() => setLocation("local")}
            />
            <LocationOption
              selected={location === "remote"}
              icon={Ic.globe(16)}
              label="Remote"
              description="Connect via SSH"
              onSelect={() => setLocation("remote")}
            />
          </div>

          {location === "remote" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={lgContentCard(0)}>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={lgStyles.fieldFrame}>
                    <span style={lgStyles.label}>Host</span>
                    <input
                      type="text"
                      value={ssh.host}
                      onChange={(e) => setSsh((s) => ({ ...s, host: e.target.value }))}
                      placeholder="user@hostname or IP"
                      style={lgInput(false)}
                    />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 100px", gap: 10 }}>
                    <div style={lgStyles.fieldFrame}>
                      <span style={lgStyles.label}>User</span>
                      <input
                        type="text"
                        value={ssh.user}
                        onChange={(e) => setSsh((s) => ({ ...s, user: e.target.value }))}
                        placeholder="ubuntu"
                        style={lgInput(false)}
                      />
                    </div>
                    <div style={lgStyles.fieldFrame}>
                      <span style={lgStyles.label}>Port</span>
                      <input
                        type="text"
                        value={ssh.port}
                        onChange={(e) => setSsh((s) => ({ ...s, port: e.target.value }))}
                        placeholder="22"
                        style={lgInput(false)}
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div style={{ ...lgInfoBanner("muted"), fontSize: 12 }}>
                <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.info(14)}</span>
                <span style={{ color: lgColors.textMid }}>
                  Remote provisioning is not yet supported. The workbench will be created locally.
                </span>
              </div>
            </div>
          )}

          <SectionLabel icon={Ic.layers(14)}>Image</SectionLabel>
          <ImageCard image={STANDARD_IMAGE} />

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
            disabled={loading || !canProvision}
            style={{ ...lgPrimaryActionButton(loading || !canProvision), justifyContent: "center" }}
          >
            {loading ? Ic.loader(15) : Ic.package(15)}
            <span>{loading ? "Powering up…" : "Provision workbench"}</span>
          </button>
          <span style={{ fontSize: 11.5, color: lgColors.textMuted, textAlign: "center" }}>
            {canProvision
              ? "Brings the lab online — this can take a moment on first run."
              : "Enter a remote host to continue."}
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
