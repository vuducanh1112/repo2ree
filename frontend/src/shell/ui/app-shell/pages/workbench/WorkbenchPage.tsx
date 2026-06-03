import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { LogEntry, LogLine } from "../../../../../core/ree/ReeTypes";
import { Ic } from "../../../shared/components/Icon";
import {
  lgColors,
  lgContentCard,
  lgGlassButton,
  lgInfoBanner,
  lgInput,
  lgPrimaryActionButton,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { SummaryLine } from "../../components/SummaryLine";
import { SummaryPanel } from "../../components/SummaryPanel";
import { APP_ROUTE } from "../../state/pages";
import {
  DetailRow,
  ImageCard,
  InfoNotePanel,
  LocationOption,
  STANDARD_IMAGE,
  WORKBENCH_COLOR,
} from "./WorkbenchPageSections";

type LocationType = "local" | "remote";

interface SshDetails {
  host: string;
  user: string;
  port: string;
}

// Consumer-owned port: the minimal capability this page needs from the runtime.
// Kept narrow on purpose so raw infra DTOs (ReeDetailDto) don't leak into the UI
// layer — see the shell-ui-no-raw-infra boundary.
interface WorkbenchApi {
  createRee(payload: { sourceMode: "upload" | "url"; name?: string }): Promise<{ reeId: string }>;
  reprovisionWorkbench(reeId: string): Promise<unknown>;
}

interface WorkbenchPageProps {
  provisioned: boolean;
  reeId: string;
  reeApi: WorkbenchApi;
  reeName?: string;
}

// Append a line to the page's client-side activity log. The provision and
// reprovision endpoints return synchronously (no streamed container logs), so
// this records the operation lifecycle the UI actually drives. The clock read
// keeps this at the shell edge rather than the pure core.
function appendLine(prev: LogEntry | null, type: LogLine["type"], msg: string): LogEntry {
  const ts = new Date().toISOString();
  return { lines: [...(prev?.lines ?? []), { type, msg, ts }], ts };
}

export function WorkbenchPage({ provisioned, reeId, reeApi, reeName }: WorkbenchPageProps) {
  const navigate = useNavigate();
  const [location, setLocation] = useState<LocationType>("local");
  const [ssh, setSsh] = useState<SshDetails>({ host: "", user: "", port: "22" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reprovisioning, setReprovisioning] = useState(false);
  const [reprovisionError, setReprovisionError] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry | null>(null);

  const provisionLabel = location === "remote" && ssh.host ? ssh.host : "this machine";

  async function handleProvision() {
    setLoading(true);
    setError(null);
    setLog(appendLine(null, "info", "Provisioning workbench…"));
    setLog((l) => appendLine(l, "out", `Image: ${STANDARD_IMAGE.ref}`));
    setLog((l) => appendLine(l, "out", `Location: ${provisionLabel}`));
    try {
      // The REE's display name is owned by the Metadata page; provision with a
      // neutral default and let the user rename it there.
      const created = await reeApi.createRee({
        sourceMode: "upload",
        name: "REE",
      });
      setLog((l) => appendLine(l, "ok", "Workbench ready — opening workspace"));
      navigate(`${APP_ROUTE.WORKSPACE}?reeId=${encodeURIComponent(created.reeId)}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Provisioning failed";
      setError(msg);
      setLog((l) => appendLine(l, "err", msg));
    } finally {
      setLoading(false);
    }
  }

  async function handleReprovision() {
    setReprovisioning(true);
    setReprovisionError(null);
    setLog(appendLine(null, "info", "Reprovisioning workbench…"));
    setLog((l) => appendLine(l, "out", `Replacing container from ${STANDARD_IMAGE.ref}`));
    setLog((l) => appendLine(l, "out", "Preserving /ree workspace volume"));
    try {
      await reeApi.reprovisionWorkbench(reeId);
      setLog((l) => appendLine(l, "ok", "Workbench reprovisioned"));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Reprovision failed";
      setReprovisionError(msg);
      setLog((l) => appendLine(l, "err", msg));
    } finally {
      setReprovisioning(false);
    }
  }

  if (provisioned) {
    return (
      <ProvisionedView
        reeName={reeName}
        location={location}
        ssh={ssh}
        reprovisioning={reprovisioning}
        reprovisionError={reprovisionError}
        log={log}
        onReprovision={handleReprovision}
      />
    );
  }

  const canProvision = location === "local" || ssh.host.trim().length > 0;
  const locationLabel = location === "remote" && ssh.host ? ssh.host : "This machine";

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.package(24)}
          title="Workbench"
          subtitle="Choose where to provision the isolated workbench that will host your REE."
          badges={<span style={lgStatusBadge(false)}>Not provisioned</span>}
        />

        <div style={lgStyles.mainGrid}>
          <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
            <div style={lgStyles.sectionBody}>
              <GlassSectionHeader
                icon={Ic.cpu(19)}
                color={WORKBENCH_COLOR}
                title="Location"
                subtitle="Where the workbench runs — the only configurable axis."
              />

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
                <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
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
                      Remote provisioning is not yet supported. The workbench will be created
                      locally.
                    </span>
                  </div>
                </div>
              )}

              <div style={{ marginTop: 26 }}>
                <GlassSectionHeader
                  icon={Ic.layers(19)}
                  color={WORKBENCH_COLOR}
                  title="Image"
                  subtitle="The base image the workbench is built from."
                />
                <ImageCard image={STANDARD_IMAGE} />
              </div>

              {error && (
                <div style={{ ...lgInfoBanner("danger"), marginTop: 18 }}>
                  <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.x(14)}</span>
                  <span style={{ fontSize: 13, color: lgColors.danger }}>{error}</span>
                </div>
              )}

              <div style={{ marginTop: 22 }}>
                <CollapsibleLogCard log={log} running={loading} title="Provisioning log" />
              </div>
            </div>

            <div style={lgStyles.footer}>
              <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
                {canProvision
                  ? "Ready to provision — this can take a moment on first run."
                  : "Enter a remote host to continue."}
              </span>
              <button
                type="button"
                onClick={handleProvision}
                disabled={loading || !canProvision}
                style={lgPrimaryActionButton(loading || !canProvision)}
              >
                {loading ? Ic.loader(15) : Ic.package(15)}
                <span>{loading ? "Provisioning…" : "Provision workbench"}</span>
              </button>
            </div>
          </section>

          <div style={lgStyles.aside}>
            <SummaryPanel title="Configuration" icon={Ic.settings(22)} iconColor={WORKBENCH_COLOR}>
              <div style={lgStyles.overviewHeader}>
                <span style={lgStyles.overviewLabel}>Overview</span>
                <span style={lgStatusBadge(false)}>Pending</span>
              </div>
              <SummaryLine
                label="Location"
                value={location === "remote" ? "Remote (SSH)" : "Local"}
              />
              <SummaryLine label="Target" value={locationLabel} />
              <SummaryLine
                label="Image"
                value={<span style={{ fontFamily: F.mono }}>{STANDARD_IMAGE.ref}</span>}
              />
            </SummaryPanel>

            <InfoNotePanel />
          </div>
        </div>
      </div>
    </div>
  );
}

interface ProvisionedViewProps {
  reeName?: string;
  location: LocationType;
  ssh: SshDetails;
  reprovisioning: boolean;
  reprovisionError: string | null;
  log: LogEntry | null;
  onReprovision: () => void;
}

function ProvisionedView({
  reeName,
  location,
  ssh,
  reprovisioning,
  reprovisionError,
  log,
  onReprovision,
}: ProvisionedViewProps) {
  const locationLabel = location === "remote" && ssh.host ? ssh.host : "Local";

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.package(24)}
          title="Workbench"
          subtitle="The workbench is provisioned and ready."
          badges={<span style={lgStatusBadge(true)}>Running</span>}
        />

        <div style={lgStyles.mainGrid}>
          <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
            <div style={lgStyles.sectionBody}>
              <GlassSectionHeader
                icon={Ic.package(19)}
                color={WORKBENCH_COLOR}
                title="Workbench Details"
                subtitle="The live sandbox hosting this REE."
              />

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <DetailRow label="REE" value={reeName || "—"} />
                <DetailRow label="Image">
                  <span style={{ fontSize: 13, color: lgColors.text, fontFamily: F.mono }}>
                    {STANDARD_IMAGE.ref}
                  </span>
                </DetailRow>
                <DetailRow label="Location" value={locationLabel} />
                <DetailRow label="Status">
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: lgColors.success,
                        boxShadow: `0 0 6px ${lgColors.success}`,
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontSize: 13, color: lgColors.success, fontWeight: 600 }}>
                      Running
                    </span>
                  </div>
                </DetailRow>
              </div>

              {reprovisionError && (
                <div style={{ ...lgInfoBanner("danger"), marginTop: 18 }}>
                  <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.x(14)}</span>
                  <span style={{ fontSize: 13, color: lgColors.danger }}>{reprovisionError}</span>
                </div>
              )}

              <div style={{ marginTop: 22 }}>
                <CollapsibleLogCard log={log} running={reprovisioning} title="Workbench log" />
              </div>
            </div>

            <div style={lgStyles.footer}>
              <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
                Reprovisioning replaces the container, keeping the /ree volume.
              </span>
              <button
                type="button"
                onClick={onReprovision}
                disabled={reprovisioning}
                style={lgGlassButton()}
              >
                {Ic.refresh(14)}
                <span style={{ marginLeft: 6 }}>
                  {reprovisioning ? "Reprovisioning…" : "Reprovision workbench"}
                </span>
              </button>
            </div>
          </section>

          <div style={lgStyles.aside}>
            <SummaryPanel title="Runtime" icon={Ic.cpu(22)} iconColor={WORKBENCH_COLOR}>
              <div style={lgStyles.overviewHeader}>
                <span style={lgStyles.overviewLabel}>Overview</span>
                <span style={lgStatusBadge(true)}>Healthy</span>
              </div>
              <SummaryLine label="REE name" value={reeName || "—"} />
              <SummaryLine label="Location" value={locationLabel} />
              <SummaryLine label="Isolation" value="Docker-in-docker sandbox" />
              <SummaryLine
                label="Image"
                value={<span style={{ fontFamily: F.mono }}>{STANDARD_IMAGE.ref}</span>}
              />
            </SummaryPanel>

            <InfoNotePanel />
          </div>
        </div>
      </div>
    </div>
  );
}
