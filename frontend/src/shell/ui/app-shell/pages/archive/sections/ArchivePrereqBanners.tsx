import { Ic } from "../../../../shared/components/Icon";
import { lgColors } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

interface ArchivePrereqBannersProps {
  capstoneReady: boolean;
  buildDone: boolean;
  sbomDone: boolean;
  activationDone: boolean;
  isSealed: boolean;
}

function PrereqChip({ label }: { label: string }) {
  return (
    <span
      style={{
        fontSize: 12,
        fontFamily: F.sans,
        fontWeight: 600,
        color: lgColors.warning,
        background: "rgba(255, 255, 255, 0.6)",
        border: "1px solid rgba(245, 158, 11, 0.45)",
        borderRadius: 6,
        padding: "2px 8px",
      }}
    >
      ✗ {label}
    </span>
  );
}

export function ArchivePrereqBanners({
  capstoneReady,
  buildDone,
  sbomDone,
  activationDone,
  isSealed,
}: ArchivePrereqBannersProps) {
  return (
    <>
      {!capstoneReady && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "12px 16px",
            marginBottom: 16,
            background: "rgba(254, 252, 232, 0.86)",
            border: "1px solid rgba(245, 158, 11, 0.42)",
            borderRadius: 10,
            boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.7)",
          }}
        >
          <span style={{ color: lgColors.warning, display: "flex", flexShrink: 0, marginTop: 1 }}>
            {Ic.info()}
          </span>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: lgColors.warning,
                marginBottom: 4,
                fontFamily: F.sans,
              }}
            >
              Complete earlier steps before depositing
            </div>
            <div
              style={{
                fontSize: 13,
                color: lgColors.textMid,
                lineHeight: 1.5,
                marginBottom: 8,
                fontFamily: F.sans,
              }}
            >
              Archiving before building and validating risks depositing an environment that can't be
              reproduced. Complete these steps first:
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {!buildDone && <PrereqChip label="Build Runtime not run" />}
              {!sbomDone && <PrereqChip label="SBOM not generated" />}
              {!activationDone && <PrereqChip label="Activation test not run" />}
            </div>
          </div>
        </div>
      )}

      {!isSealed && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "12px 16px",
            marginBottom: 16,
            background: "rgba(239, 246, 255, 0.86)",
            border: "1px solid rgba(125, 211, 252, 0.5)",
            borderRadius: 10,
            boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.7)",
          }}
        >
          <span style={{ color: lgColors.blue, display: "flex", flexShrink: 0, marginTop: 1 }}>
            {Ic.info()}
          </span>
          <div
            style={{
              flex: 1,
              fontSize: 13,
              color: lgColors.textMid,
              lineHeight: 1.5,
              fontFamily: F.sans,
            }}
          >
            Deposit can proceed before sealing, but the final Seal step is still required before
            your REE is considered complete.
          </div>
        </div>
      )}
    </>
  );
}
