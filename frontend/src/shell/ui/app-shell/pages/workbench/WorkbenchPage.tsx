import type React from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Ic } from "../../../shared/components/Icon";
import {
  lgBackgrounds,
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
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { APP_ROUTE } from "../../state/pages";

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
  createRee(payload: {
    sourceMode: "upload" | "url" | "demo";
    name?: string;
  }): Promise<{ reeId: string }>;
  reprovisionWorkbench(reeId: string): Promise<unknown>;
}

interface WorkbenchPageProps {
  provisioned: boolean;
  reeId: string;
  reeApi: WorkbenchApi;
  reeName?: string;
}

export function WorkbenchPage({ provisioned, reeId, reeApi, reeName }: WorkbenchPageProps) {
  const navigate = useNavigate();
  const [location, setLocation] = useState<LocationType>("local");
  const [ssh, setSsh] = useState<SshDetails>({ host: "", user: "", port: "22" });
  const [name, setName] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reprovisioning, setReprovisioning] = useState(false);
  const [reprovisionError, setReprovisionError] = useState<string | null>(null);

  async function handleProvision() {
    setLoading(true);
    setError(null);
    try {
      const created = await reeApi.createRee({
        sourceMode: "upload",
        name: name.trim() || "REE Workspace",
      });
      navigate(`${APP_ROUTE.WORKSPACE}?reeId=${encodeURIComponent(created.reeId)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Provisioning failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleReprovision() {
    setReprovisioning(true);
    setReprovisionError(null);
    try {
      await reeApi.reprovisionWorkbench(reeId);
    } catch (err) {
      setReprovisionError(err instanceof Error ? err.message : "Reprovision failed");
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
        onReprovision={handleReprovision}
      />
    );
  }

  const canProvision = location === "local" || ssh.host.trim().length > 0;

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.package(24)}
          title="Workbench"
          subtitle="Choose where to provision the isolated workbench that will host your REE."
        />

        <div style={{ maxWidth: 540, display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={lgStyles.panel}>
            <div style={lgStyles.sectionBody}>
              <div style={lgStyles.sectionHeader}>
                <div style={lgStyles.sectionIcon}>{Ic.file(19)}</div>
                <div>
                  <h2 style={lgStyles.sectionTitle}>REE Name</h2>
                  <div style={lgStyles.sectionSubtitle}>
                    Human-readable label for this workbench
                  </div>
                </div>
              </div>
              <input
                id="ree-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="REE Workspace"
                style={lgInput(false)}
              />
            </div>
          </div>

          <div style={lgStyles.panel}>
            <div style={lgStyles.sectionBody}>
              <div style={lgStyles.sectionHeader}>
                <div style={lgStyles.sectionIcon}>{Ic.cpu(19)}</div>
                <div>
                  <h2 style={lgStyles.sectionTitle}>Location</h2>
                  <div style={lgStyles.sectionSubtitle}>Where the workbench container will run</div>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <LocationOption
                  id="local"
                  selected={location === "local"}
                  icon={Ic.cpu(16)}
                  label="Local"
                  description="Run on this machine"
                  onSelect={() => setLocation("local")}
                />
                <LocationOption
                  id="remote"
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
            </div>
          </div>

          {error && (
            <div style={lgInfoBanner("danger")}>
              <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.x(14)}</span>
              <span style={{ fontSize: 13, color: lgColors.danger }}>{error}</span>
            </div>
          )}

          <div>
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
        </div>
      </div>
    </div>
  );
}

interface LocationOptionProps {
  id: LocationType;
  selected: boolean;
  icon: React.ReactNode;
  label: string;
  description: string;
  onSelect: () => void;
}

function LocationOption({ selected, icon, label, description, onSelect }: LocationOptionProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 14px",
        borderRadius: 9,
        border: selected
          ? "1.5px solid rgba(14, 165, 233, 0.58)"
          : "1.5px solid rgba(125, 211, 252, 0.38)",
        background: selected ? "rgba(239, 246, 255, 0.94)" : lgBackgrounds.glassStrong,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.14s",
        boxShadow: selected ? "0 8px 20px rgba(14, 165, 233, 0.12)" : "none",
        fontFamily: F.sans,
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 9,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: selected ? lgColors.primaryDeep : lgColors.textMid,
          background: selected ? lgBackgrounds.primary : lgBackgrounds.iconSoft,
          border: selected
            ? "1px solid rgba(14, 165, 233, 0.35)"
            : "1px solid rgba(125, 211, 252, 0.38)",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 14,
            fontWeight: selected ? 700 : 500,
            color: selected ? lgColors.primaryDeep : lgColors.text,
          }}
        >
          {label}
        </div>
        <div style={{ fontSize: 12, color: lgColors.textMuted, marginTop: 1 }}>{description}</div>
      </div>
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: "50%",
          border: `2px solid ${selected ? lgColors.blue : "rgba(148, 163, 184, 0.5)"}`,
          background: selected ? lgColors.blue : "transparent",
          flexShrink: 0,
          boxShadow: selected ? `0 0 8px ${lgColors.blue}66` : "none",
          transition: "all 0.14s",
        }}
      />
    </button>
  );
}

interface ProvisionedViewProps {
  reeName?: string;
  location: LocationType;
  ssh: SshDetails;
  reprovisioning: boolean;
  reprovisionError: string | null;
  onReprovision: () => void;
}

function ProvisionedView({
  reeName,
  location,
  ssh,
  reprovisioning,
  reprovisionError,
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

        <div style={{ maxWidth: 540, display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={lgStyles.panel}>
            <div style={lgStyles.sectionBody}>
              <div style={lgStyles.sectionHeader}>
                <div style={lgStyles.sectionIcon}>{Ic.package(19)}</div>
                <div>
                  <h2 style={lgStyles.sectionTitle}>Workbench Details</h2>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <DetailRow label="REE" value={reeName || "—"} />
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
            </div>
          </div>

          {reprovisionError && (
            <div style={lgInfoBanner("danger")}>
              <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.x(14)}</span>
              <span style={{ fontSize: 13, color: lgColors.danger }}>{reprovisionError}</span>
            </div>
          )}

          <div>
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
        </div>
      </div>
    </div>
  );
}

function DetailRow({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "9px 12px",
        borderRadius: 8,
        background: lgBackgrounds.row,
        border: "1px solid rgba(148, 163, 184, 0.3)",
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: lgColors.textMuted,
          fontFamily: F.mono,
          minWidth: 72,
          flexShrink: 0,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {label}
      </span>
      {children ?? <span style={{ fontSize: 13, color: lgColors.text }}>{value}</span>}
    </div>
  );
}
