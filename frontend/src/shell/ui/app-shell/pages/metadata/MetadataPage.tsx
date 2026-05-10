import type React from "react";
import { useMemo, useState } from "react";
import {
  addCatalogContributor,
  addCatalogKeyword,
  patchCatalogMetadata,
  removeCatalogContributor,
  removeCatalogKeyword,
  setCorrespondingCatalogContributor,
  updateCatalogContributor,
} from "../../../../../core/ree/catalogMetadataOps";
import type { ReeContributor } from "../../../../../core/ree/ReeSpec";
import { Ic } from "../../../shared/components/Icon";
import { useFocusScroll } from "../../../shared/hooks/useFocusScroll";
import {
  LGC,
  LGS,
  lgActionButton,
  lgCorrespondingBadge,
  lgGlassButton,
  lgInput,
  lgNextButton,
  lgReadout,
  lgStatusBadge,
  lgSuggestionButton,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { assemblyToneSurfaceStyle } from "../../components/statusUiStyles";
import { PAGE } from "../../state/pages";
import type { PageMetadataEntryProps } from "../sharedAssemblyUi";

function MetadataField({
  label,
  required,
  help,
  children,
}: {
  label: string;
  required?: boolean;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={LGS.fieldFrame}>
      <span style={LGS.label}>
        {label}
        {required && <span style={{ color: LGC.required }}>*</span>}
        <span style={{ color: LGC.blue, display: "flex" }}>{Ic.info(12)}</span>
      </span>
      {children}
      {help && <span style={LGS.helper}>{help}</span>}
    </div>
  );
}

function MetadataChip({ children }: { children: React.ReactNode }) {
  return <span style={LGS.chip}>{children}</span>;
}

const KEYWORD_SUGGESTIONS = [
  "reusable-execution-environment",
  "provenance",
  "reproducibility",
  "containerized-runtime",
  "workflow-automation",
  "scientific-computing",
];

function SummaryLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <span style={{ fontSize: 11, color: LGC.textMuted, fontFamily: F.sans }}>{label}</span>
      <span
        style={{
          fontSize: 13,
          color: LGC.text,
          fontFamily: F.sans,
          lineHeight: 1.35,
          overflowWrap: "anywhere",
        }}
      >
        {value}
      </span>
    </div>
  );
}

export function PageMetadataEntry({
  reeSpec,
  locked,
  badges,
  focusedField,
  onReeChange,
  onLockedChange,
  onGoAssemblyPage,
  onFocusedFieldChange,
}: PageMetadataEntryProps) {
  const set = <K extends keyof typeof reeSpec>(k: K, v: (typeof reeSpec)[K]) =>
    onReeChange((current) => ({ ...current, [k]: v }) as typeof reeSpec);
  const focus = (key: string) => onFocusedFieldChange(key);
  const metadata = reeSpec.catalog_metadata;
  const [pendingContributor, setPendingContributor] = useState<ReeContributor>({
    identifier: "",
    name: "",
    affiliation_name: "",
    affiliation_identifier: "",
  });
  const [contributorAddError, setContributorAddError] = useState("");
  const [editingContributorId, setEditingContributorId] = useState<string | null>(null);
  const [contributorDraft, setContributorDraft] = useState<ReeContributor>({
    identifier: "",
    name: "",
    affiliation_name: "",
    affiliation_identifier: "",
  });
  const [pendingKeyword, setPendingKeyword] = useState("");

  useFocusScroll(focusedField);

  const { description, version, website, keywords, contributors } = metadata;
  const correspondingAuthor = metadata.corresponding_author_identifier || "";
  const archiveId = reeSpec.zenodo_doi || reeSpec.dataverse_doi || "Assigned during deposit";
  const identityFilled = reeSpec.name.trim().length > 0;
  const descriptionFilled = description.trim().length > 0;
  const versionFilled = version.trim().length > 0;
  const correspondingAuthorFilled =
    correspondingAuthor.trim().length > 0 &&
    contributors.some((item) => item.identifier === correspondingAuthor);
  const hasKeywords = keywords.length > 0;
  const completionCount = [
    identityFilled,
    descriptionFilled,
    versionFilled,
    hasKeywords,
    correspondingAuthorFilled,
  ].filter(Boolean).length;
  const completionPct = Math.round((completionCount / 5) * 100);
  const requiredTotal = 3;
  const requiredDone = [identityFilled, descriptionFilled, versionFilled].filter(Boolean).length;
  const availableSuggestions = useMemo(
    () => KEYWORD_SUGGESTIONS.filter((kw) => !keywords.includes(kw)),
    [keywords],
  );

  const addKeyword = (raw: string) => {
    if (locked) return;
    onReeChange((current) => addCatalogKeyword(current, raw));
    setPendingKeyword("");
  };

  const removeKeyword = (keyword: string) => {
    if (locked) return;
    onReeChange((current) => removeCatalogKeyword(current, keyword));
  };

  const addContributor = () => {
    if (locked) return;
    const result = addCatalogContributor(reeSpec, pendingContributor);
    if (!result.ok) {
      setContributorAddError(result.error);
      return;
    }
    onReeChange((current) => {
      const currentResult = addCatalogContributor(current, pendingContributor);
      return currentResult.ok ? currentResult.spec : current;
    });
    setPendingContributor({
      identifier: "",
      name: "",
      affiliation_name: "",
      affiliation_identifier: "",
    });
    setContributorAddError("");
  };

  const removeContributor = (identifier: string) => {
    if (locked) return;
    onReeChange((current) => removeCatalogContributor(current, identifier));
    if (editingContributorId === identifier) {
      setEditingContributorId(null);
    }
  };

  const editContributor = (contributor: ReeContributor) => {
    if (locked) return;
    setEditingContributorId(contributor.identifier);
    setContributorDraft({ ...contributor });
  };

  const saveContributor = () => {
    if (locked || !editingContributorId) return;
    const result = updateCatalogContributor(reeSpec, editingContributorId, contributorDraft);
    if (!result.ok) {
      setContributorAddError(result.error);
      return;
    }
    onReeChange((current) => {
      const currentResult = updateCatalogContributor(
        current,
        editingContributorId,
        contributorDraft,
      );
      return currentResult.ok ? currentResult.spec : current;
    });
    setContributorAddError("");
    setEditingContributorId(null);
  };

  const cancelContributorEdit = () => {
    setEditingContributorId(null);
    setContributorDraft({
      identifier: "",
      name: "",
      affiliation_name: "",
      affiliation_identifier: "",
    });
  };

  return (
    <div style={LGS.pageRoot}>
      <div style={LGS.pageFrame}>
        <div style={LGS.pageHeader}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
            <div style={LGS.headerIcon}>{Ic.grid(24)}</div>
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  flexWrap: "wrap",
                  marginBottom: 4,
                }}
              >
                <h1 style={LGS.title}>Metadata</h1>
                <span style={lgStatusBadge(identityFilled)}>
                  {identityFilled ? "Ready" : "Draft"}
                </span>
              </div>
              <p style={LGS.subtitle}>
                Provide the identity details that follow this Reusable Execution Environment through
                the assembly workflow.
              </p>
            </div>
          </div>

          {locked ? (
            <button
              type="button"
              onClick={() => onLockedChange(false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 12px",
                ...assemblyToneSurfaceStyle("warn"),
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 13,
                fontFamily: F.sans,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {Ic.unlock(13)} Unlock fields
            </button>
          ) : null}
        </div>

        <div style={LGS.mainGrid}>
          <section style={{ ...LGS.panel, overflow: "hidden" }}>
            <div style={LGS.sectionBody}>
              <div style={LGS.sectionHeader}>
                <div style={LGS.sectionIcon}>{Ic.file(19)}</div>
                <div>
                  <h2 style={LGS.sectionTitle}>Metadata Entry</h2>
                  <div style={LGS.sectionSubtitle}>Stable naming and provenance context</div>
                </div>
              </div>

              <div style={LGS.fieldsGrid}>
                <MetadataField
                  label="REE Name"
                  required
                  help="Use a stable, descriptive name. Include a version suffix if that is part of your project convention."
                >
                  <input
                    id="field-name"
                    disabled={locked}
                    value={reeSpec.name}
                    onChange={(event) => set("name", event.target.value)}
                    onFocus={() => focus("name")}
                    placeholder="deepfold-protein-structure-prediction"
                    style={lgInput(locked, focusedField === "name")}
                  />
                </MetadataField>

                <MetadataField
                  label="Version"
                  required
                  help="Semantic version of this REE snapshot."
                >
                  <input
                    disabled={locked}
                    value={version}
                    onChange={(event) =>
                      onReeChange((current) =>
                        patchCatalogMetadata(current, { version: event.target.value }),
                      )
                    }
                    onFocus={() => focus("catalog_metadata.version")}
                    placeholder="1.0.0"
                    style={lgInput(locked)}
                  />
                </MetadataField>

                <MetadataField
                  label="Website"
                  help="Project page, documentation, or repository landing page."
                >
                  <input
                    disabled={locked}
                    value={website}
                    onChange={(event) =>
                      onReeChange((current) =>
                        patchCatalogMetadata(current, { website: event.target.value }),
                      )
                    }
                    onFocus={() => focus("catalog_metadata.website")}
                    placeholder="https://example.org/project"
                    style={lgInput(locked)}
                  />
                </MetadataField>

                <MetadataField
                  label="Description"
                  required
                  help="Capture what this REE does, for whom, and any key assumptions."
                >
                  <textarea
                    value={description}
                    onChange={(event) =>
                      onReeChange((current) =>
                        patchCatalogMetadata(current, { description: event.target.value }),
                      )
                    }
                    onFocus={() => focus("catalog_metadata.description")}
                    placeholder="REE for reproducible execution of..."
                    style={{
                      ...lgInput(locked, false),
                      minHeight: 112,
                      resize: "vertical",
                      lineHeight: 1.45,
                    }}
                    disabled={locked}
                  />
                </MetadataField>
              </div>

              <div style={LGS.firstContentCard}>
                <div style={{ ...LGS.label, marginBottom: 10 }}>Keywords</div>
                <div style={LGS.chipRow}>
                  {keywords.map((keyword) => (
                    <span key={keyword} style={LGS.inlineChipWrap}>
                      <MetadataChip>{keyword}</MetadataChip>
                      {!locked && (
                        <button
                          type="button"
                          onClick={() => removeKeyword(keyword)}
                          style={LGS.iconRemoveSmall}
                          aria-label={`Remove keyword ${keyword}`}
                        >
                          {Ic.x(12)}
                        </button>
                      )}
                    </span>
                  ))}
                </div>
                {!locked && (
                  <div style={LGS.keywordControls}>
                    <div style={LGS.flexWrapRow}>
                      <input
                        value={pendingKeyword}
                        onChange={(event) => setPendingKeyword(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            addKeyword(pendingKeyword);
                          }
                        }}
                        placeholder="Add custom keyword"
                        style={{ ...lgInput(false), minHeight: 38, flex: "1 1 220px" }}
                      />
                      <button
                        type="button"
                        onClick={() => addKeyword(pendingKeyword)}
                        style={lgGlassButton()}
                      >
                        Add keyword
                      </button>
                    </div>
                    {availableSuggestions.length > 0 && (
                      <div style={LGS.suggestionWrap}>
                        {availableSuggestions.map((keyword) => (
                          <button
                            key={keyword}
                            type="button"
                            onClick={() => addKeyword(keyword)}
                            style={lgSuggestionButton()}
                          >
                            + {keyword}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {locked && <div style={LGS.helper}>Unlock fields to add or remove keywords.</div>}
                {keywords.length === 0 && (
                  <div style={LGS.helper}>
                    No keywords yet. Add at least one for discoverability.
                  </div>
                )}
              </div>

              <div style={LGS.contentCard}>
                <div style={{ ...LGS.label, marginBottom: 10 }}>Contributors</div>

                {contributors.length > 0 && (
                  <div style={LGS.contributorList}>
                    {contributors.map((contributor) => (
                      <div key={`${contributor.identifier}-detail`} style={LGS.contributorCard}>
                        <div style={LGS.contributorHeader}>
                          <strong style={{ color: LGC.text, fontSize: 13 }}>
                            {contributor.name}
                          </strong>
                          {correspondingAuthor === contributor.identifier && (
                            <span style={lgCorrespondingBadge()}>{Ic.check(11)} Corresponding</span>
                          )}
                        </div>
                        {editingContributorId === contributor.identifier ? (
                          <div style={LGS.contributorFieldsGrid}>
                            <input
                              value={contributorDraft.identifier}
                              onChange={(event) =>
                                setContributorDraft((prev) => ({
                                  ...prev,
                                  identifier: event.target.value,
                                }))
                              }
                              placeholder="Identifier"
                              style={{ ...lgInput(false), minHeight: 38 }}
                            />
                            <input
                              value={contributorDraft.name}
                              onChange={(event) =>
                                setContributorDraft((prev) => ({
                                  ...prev,
                                  name: event.target.value,
                                }))
                              }
                              placeholder="Name"
                              style={{ ...lgInput(false), minHeight: 38 }}
                            />
                            <input
                              value={contributorDraft.affiliation_name}
                              onChange={(event) =>
                                setContributorDraft((prev) => ({
                                  ...prev,
                                  affiliation_name: event.target.value,
                                }))
                              }
                              placeholder="Affiliation name"
                              style={{ ...lgInput(false), minHeight: 38 }}
                            />
                            <input
                              value={contributorDraft.affiliation_identifier}
                              onChange={(event) =>
                                setContributorDraft((prev) => ({
                                  ...prev,
                                  affiliation_identifier: event.target.value,
                                }))
                              }
                              placeholder="Affiliation identifier"
                              style={{ ...lgInput(false), minHeight: 38 }}
                            />
                          </div>
                        ) : (
                          <div style={LGS.contributorFieldsGrid}>
                            <div style={LGS.helper}>
                              <strong style={{ color: LGC.text }}>Identifier:</strong>{" "}
                              {contributor.identifier}
                            </div>
                            <div style={LGS.helper}>
                              <strong style={{ color: LGC.text }}>Name:</strong> {contributor.name}
                            </div>
                            <div style={LGS.helper}>
                              <strong style={{ color: LGC.text }}>Affiliation Name:</strong>{" "}
                              {contributor.affiliation_name || "Not set"}
                            </div>
                            <div style={LGS.helper}>
                              <strong style={{ color: LGC.text }}>Affiliation Identifier:</strong>{" "}
                              {contributor.affiliation_identifier || "Not set"}
                            </div>
                          </div>
                        )}
                        <div style={LGS.contributorActions}>
                          {editingContributorId === contributor.identifier ? (
                            <>
                              <button
                                type="button"
                                onClick={saveContributor}
                                style={lgActionButton("primary")}
                                aria-label={`Save contributor ${contributor.name}`}
                                title="Save"
                              >
                                {Ic.check(14)}
                              </button>
                              <button
                                type="button"
                                onClick={cancelContributorEdit}
                                style={lgActionButton("neutral")}
                                aria-label={`Cancel editing contributor ${contributor.name}`}
                                title="Cancel"
                              >
                                {Ic.x(14)}
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                disabled={locked}
                                onClick={() => editContributor(contributor)}
                                style={lgActionButton("primary", locked)}
                                aria-label={`Edit contributor ${contributor.name}`}
                                title="Edit"
                              >
                                {Ic.pen(14)}
                              </button>
                              <button
                                type="button"
                                disabled={locked}
                                onClick={() => removeContributor(contributor.identifier)}
                                style={lgActionButton("danger", locked)}
                                aria-label={`Remove contributor ${contributor.name}`}
                                title="Remove"
                              >
                                {Ic.x(14)}
                              </button>
                              <button
                                type="button"
                                disabled={locked || correspondingAuthor === contributor.identifier}
                                onClick={() =>
                                  onReeChange((current) =>
                                    setCorrespondingCatalogContributor(
                                      current,
                                      contributor.identifier,
                                    ),
                                  )
                                }
                                style={lgActionButton(
                                  "success",
                                  locked || correspondingAuthor === contributor.identifier,
                                )}
                                aria-label={
                                  correspondingAuthor === contributor.identifier
                                    ? `${contributor.name} is corresponding author`
                                    : `Designate ${contributor.name} as corresponding author`
                                }
                                title={
                                  correspondingAuthor === contributor.identifier
                                    ? "Corresponding"
                                    : "Designate as corresponding"
                                }
                              >
                                {correspondingAuthor === contributor.identifier
                                  ? Ic.check(14)
                                  : Ic.star(14)}
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {!locked && (
                  <div style={LGS.contributorAddGrid}>
                    <input
                      value={pendingContributor.identifier}
                      onChange={(event) =>
                        setPendingContributor((prev) => ({
                          ...prev,
                          identifier: event.target.value,
                        }))
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          addContributor();
                        }
                      }}
                      placeholder="Identifier"
                      style={{ ...lgInput(false), minHeight: 38 }}
                    />
                    <input
                      value={pendingContributor.name}
                      onChange={(event) =>
                        setPendingContributor((prev) => ({ ...prev, name: event.target.value }))
                      }
                      placeholder="Name *"
                      aria-required="true"
                      style={{ ...lgInput(false), minHeight: 38 }}
                    />
                    <input
                      value={pendingContributor.affiliation_name}
                      onChange={(event) =>
                        setPendingContributor((prev) => ({
                          ...prev,
                          affiliation_name: event.target.value,
                        }))
                      }
                      placeholder="Affiliation name"
                      style={{ ...lgInput(false), minHeight: 38 }}
                    />
                    <input
                      value={pendingContributor.affiliation_identifier}
                      onChange={(event) =>
                        setPendingContributor((prev) => ({
                          ...prev,
                          affiliation_identifier: event.target.value,
                        }))
                      }
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          addContributor();
                        }
                      }}
                      placeholder="Affiliation identifier"
                      style={{ ...lgInput(false), minHeight: 38 }}
                    />
                  </div>
                )}
                {contributorAddError && (
                  <div style={{ ...LGS.helper, color: LGC.danger, marginTop: 8 }}>
                    {contributorAddError}
                  </div>
                )}
                {!locked && (
                  <div style={{ marginTop: 8 }}>
                    <button type="button" onClick={addContributor} style={lgGlassButton()}>
                      Add contributor entity
                    </button>
                  </div>
                )}
                {contributors.length === 0 && <div style={LGS.helper}>No contributors yet.</div>}
              </div>
            </div>

            <div style={LGS.footer}>
              <span style={{ color: LGC.textMuted, fontSize: 12 }}>
                <span style={{ color: LGC.required }}>*</span> Required fields
              </span>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => onGoAssemblyPage(PAGE.HBOM)}
                  style={lgNextButton()}
                >
                  Next: Hardware {Ic.chevR(15)}
                </button>
              </div>
            </div>
          </section>

          <aside style={LGS.aside}>
            <section style={{ ...LGS.panel, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                <span style={{ color: LGC.cyan, display: "flex" }}>{Ic.package(22)}</span>
                <h2 style={{ margin: 0, fontSize: 15, color: LGC.text }}>REE Summary</h2>
              </div>

              <div style={LGS.summaryBox}>
                <div style={LGS.overviewHeader}>
                  <span style={LGS.overviewLabel}>Overview</span>
                  <span style={lgStatusBadge(identityFilled)}>
                    {identityFilled ? "Live" : "Needs name"}
                  </span>
                </div>
                <SummaryLine label="Name" value={reeSpec.name || "Untitled REE"} />
                <SummaryLine label="Version" value={version || "Not set"} />
                <SummaryLine label="Website" value={website || "Not set"} />
                <SummaryLine
                  label="Description"
                  value={description || "No description provided yet"}
                />
                <SummaryLine
                  label="Contributors"
                  value={
                    contributors.length
                      ? contributors.map((item) => `${item.name} [${item.identifier}]`).join(", ")
                      : "None"
                  }
                />
                <SummaryLine
                  label="Keywords"
                  value={keywords.length ? keywords.join(", ") : "None"}
                />
                <SummaryLine label="Archive" value={archiveId} />
                <SummaryLine
                  label="Workflow"
                  value={badges.hbom ? "Hardware BOM started" : "Ready for hardware"}
                />
              </div>
            </section>

            <section style={{ ...LGS.panel, padding: 16 }}>
              <div style={LGS.readinessHeader}>
                <span>Metadata Readiness</span>
                <span style={{ color: LGC.blue, fontFamily: F.mono }}>{completionPct}%</span>
              </div>
              <div style={LGS.progressTrack}>
                <div
                  style={{
                    ...LGS.progressFill,
                    width: `${completionPct}%`,
                  }}
                />
              </div>
              <div style={LGS.statGrid}>
                <div
                  style={{
                    ...lgReadout(LGS.statReadout),
                  }}
                >
                  <span style={{ color: LGC.textMuted, fontSize: 11 }}>Required</span>
                  <strong style={{ color: LGC.text, fontSize: 18 }}>
                    {requiredDone}/{requiredTotal}
                  </strong>
                </div>
                <div
                  style={{
                    ...lgReadout(LGS.statReadout),
                  }}
                >
                  <span style={{ color: LGC.textMuted, fontSize: 11 }}>Context</span>
                  <strong style={{ color: LGC.text, fontSize: 18 }}>{completionCount}/5</strong>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
