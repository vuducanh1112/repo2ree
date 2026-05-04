import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";

interface RvProvenanceChainProps {
  ree: ReeViewState;
}

export function RvProvenanceChain({ ree }: RvProvenanceChainProps) {
  const nodes = [
    {
      label: "Source Code",
      value: ree.origin_url,
      icon: Ic.link,
      color: "#0891b2",
      href: ree.origin_url,
    },
    {
      label: "Software Heritage",
      value: ree.swhid,
      icon: Ic.archive,
      color: "#e4572e",
      href: ree.swhid ? `https://archive.softwareheritage.org/${ree.swhid}` : null,
    },
    {
      label: "Zenodo DOI",
      value: ree.zenodo_doi,
      icon: Ic.globe,
      color: "#1d6fa4",
      href: ree.zenodo_doi ? `https://doi.org/${ree.zenodo_doi}` : null,
    },
    { label: "SBOM", value: ree.sbom, icon: Ic.package, color: "#16a34a" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {nodes.map((node, i) => {
        const set = !!node.value;
        const nodeValue = node.value ?? "";
        return (
          <div key={node.label} style={{ display: "flex", gap: 10, alignItems: "stretch" }}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: 24,
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  background: set ? `${node.color}18` : C.surfaceAlt,
                  border: `2px solid ${set ? node.color : C.borderMid}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: set ? node.color : C.textMuted,
                  flexShrink: 0,
                }}
              >
                {node.icon(9)}
              </div>
              {i < nodes.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    width: 2,
                    background: set ? `${node.color}40` : C.border,
                    minHeight: 10,
                  }}
                />
              )}
            </div>
            <div
              style={{
                flex: 1,
                paddingBottom: i < nodes.length - 1 ? 10 : 0,
                paddingTop: 1,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: set ? C.textMid : C.textMuted,
                  fontFamily: F.sans,
                  marginBottom: 1,
                }}
              >
                {node.label}
              </div>
              {set ? (
                node.href ? (
                  <a
                    href={node.href}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: node.color,
                      textDecoration: "none",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                      maxWidth: "100%",
                    }}
                  >
                    {nodeValue.length > 50 ? `${nodeValue.slice(0, 50)}…` : nodeValue}
                  </a>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: node.color,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                    }}
                  >
                    {nodeValue}
                  </span>
                )
              ) : (
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: F.sans,
                    color: C.textMuted,
                    fontStyle: "italic",
                  }}
                >
                  not set
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
