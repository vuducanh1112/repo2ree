import { Ic } from "../../../../shared/components/Icon";
import { F, S_FLEX_ROW_GAP_8 } from "../../../../theme/theme";

interface ArchivePrereqBannersProps {
  capstoneReady: boolean;
  buildDone: boolean;
  sbomDone: boolean;
  activationDone: boolean;
  isSealed: boolean;
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
            marginBottom: 20,
            background: "#fffbeb",
            border: "1px solid #fde68a",
            borderRadius: 10,
          }}
        >
          <span style={{ color: "#b45309", display: "flex", flexShrink: 0, marginTop: 1 }}>
            {Ic.info()}
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#92400e", marginBottom: 4 }}>
              Complete earlier steps before depositing
            </div>
            <div style={{ fontSize: 13, color: "#92400e", lineHeight: 1.5, marginBottom: 8 }}>
              Archiving before building and validating risks depositing an environment that can't be
              reproduced. Complete these steps first:
            </div>
            <div style={S_FLEX_ROW_GAP_8}>
              {!buildDone && (
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#92400e",
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  ✗ Build Runtime not run
                </span>
              )}
              {!sbomDone && (
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#92400e",
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  ✗ SBOM not generated
                </span>
              )}
              {!activationDone && (
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.sans,
                    color: "#92400e",
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    borderRadius: 4,
                    padding: "2px 8px",
                    fontWeight: 600,
                  }}
                >
                  ✗ Activation test not run
                </span>
              )}
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
            marginBottom: 20,
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 10,
          }}
        >
          <span style={{ color: "#1d4ed8", display: "flex", flexShrink: 0, marginTop: 1 }}>
            {Ic.info()}
          </span>
          <div style={{ flex: 1, fontSize: 13, color: "#1e3a8a", lineHeight: 1.5 }}>
            Deposit can proceed before sealing, but the final Seal step is still required before
            your REE is considered complete.
          </div>
        </div>
      )}
    </>
  );
}
