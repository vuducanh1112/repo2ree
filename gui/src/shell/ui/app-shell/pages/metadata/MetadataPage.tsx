import {
  addCatalogContributor,
  addCatalogKeyword,
  isCatalogMetadataComplete,
  patchCatalogMetadata,
  removeCatalogContributor,
  removeCatalogKeyword,
  setCorrespondingCatalogContributor,
  updateCatalogContributor,
} from "@core/ree/catalogMetadataOps";
import type { ReeContributor } from "@core/ree/ReeSpec";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Button } from "@shell/ui/shared/components/Button";
import { Field, Input, Textarea } from "@shell/ui/shared/components/FormControl";
import { Ic } from "@shell/ui/shared/components/Icon";
import { useFocusScroll } from "@shell/ui/shared/hooks/useFocusScroll";
import { type ReactNode, useMemo, useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassPageShell } from "../../components/GlassPageShell";
import type { PageMetadataEntryProps } from "../sharedStepUi";
import styles from "./MetadataPage.module.css";

function MetadataChip({ children }: { children: ReactNode }) {
  return <span className={styles.chip}>{children}</span>;
}

const KEYWORD_SUGGESTIONS = [
  "reusable-execution-environment",
  "provenance",
  "reproducibility",
  "containerized-runtime",
  "workflow-automation",
  "scientific-computing",
];

type ContributorError = {
  context: "add" | "edit";
  field: "identifier" | "name";
  message: string;
};

function contributorError(
  message: string,
  context: ContributorError["context"],
  contributor: ReeContributor,
): ContributorError {
  return {
    context,
    field: contributor.name.trim() === "" ? "name" : "identifier",
    message,
  };
}

export function PageMetadataEntry({
  reeSpec,
  locked,
  focusedField,
  onReeChange,
  onFocusedFieldChange,
}: PageMetadataEntryProps) {
  const set = <K extends keyof typeof reeSpec>(k: K, v: (typeof reeSpec)[K]) =>
    onReeChange((current) => ({ ...current, [k]: v }) as typeof reeSpec);
  const focus = (key: string) => onFocusedFieldChange(key);
  const metadata = reeSpec.catalogMetadata;
  const [pendingContributor, setPendingContributor] = useState<ReeContributor>({
    identifier: "",
    name: "",
    affiliationName: "",
    affiliationIdentifier: "",
  });
  const [contributorValidationError, setContributorValidationError] =
    useState<ContributorError | null>(null);
  const [editingContributorId, setEditingContributorId] = useState<string | null>(null);
  const [contributorDraft, setContributorDraft] = useState<ReeContributor>({
    identifier: "",
    name: "",
    affiliationName: "",
    affiliationIdentifier: "",
  });
  const [pendingKeyword, setPendingKeyword] = useState("");

  useFocusScroll(focusedField);

  const { description, version, website, keywords, contributors } = metadata;
  const correspondingAuthor = metadata.correspondingAuthorIdentifier || "";
  // Same rule the canvas node reads for this step's doneness — metadata has no
  // receipt behind it, so "every required field filled" is the whole verdict.
  const identityFilled = isCatalogMetadataComplete(reeSpec);
  const contributorFieldError = (
    context: ContributorError["context"],
    field: ContributorError["field"],
  ) =>
    contributorValidationError?.context === context && contributorValidationError.field === field
      ? contributorValidationError.message
      : undefined;
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
      setContributorValidationError(contributorError(result.error, "add", pendingContributor));
      return;
    }
    onReeChange(() => result.spec);
    setPendingContributor({
      identifier: "",
      name: "",
      affiliationName: "",
      affiliationIdentifier: "",
    });
    setContributorValidationError(null);
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
    setContributorValidationError(null);
  };

  const saveContributor = () => {
    if (locked || !editingContributorId) return;
    const result = updateCatalogContributor(reeSpec, editingContributorId, contributorDraft);
    if (!result.ok) {
      setContributorValidationError(contributorError(result.error, "edit", contributorDraft));
      return;
    }
    onReeChange(() => result.spec);
    setContributorValidationError(null);
    setEditingContributorId(null);
  };

  const cancelContributorEdit = () => {
    setEditingContributorId(null);
    setContributorValidationError(null);
    setContributorDraft({
      identifier: "",
      name: "",
      affiliationName: "",
      affiliationIdentifier: "",
    });
  };

  return (
    // Minimal form sitting directly on the focus dock — no nested frame/panel
    // layers. The dock supplies the floating surface over the canvas; the page
    // only paints its own content.
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={Ic.grid(24)}
        title="Metadata"
        subtitle="Provide the identity details that follow this Reusable Execution Environment through every step to the seal."
        badges={
          <Badge tone={identityFilled ? "success" : "warning"}>
            {identityFilled ? "Ready" : "Draft"}
          </Badge>
        }
      />

      <div className={styles.stack}>
        <div className={styles.fieldsGrid}>
          <Field
            label="REE Name"
            required
            hint="Use a stable, descriptive name. Include a version suffix if that is part of your project convention."
          >
            {(bound) => (
              <Input
                {...bound}
                disabled={locked}
                value={reeSpec.name}
                onChange={(event) => set("name", event.target.value)}
                onFocus={() => focus("name")}
                placeholder="deepfold-protein-structure-prediction"
              />
            )}
          </Field>

          <Field label="Version" required hint="Semantic version of this REE snapshot.">
            {(bound) => (
              <Input
                {...bound}
                disabled={locked}
                value={version}
                onChange={(event) =>
                  onReeChange((current) =>
                    patchCatalogMetadata(current, { version: event.target.value }),
                  )
                }
                onFocus={() => focus("catalogMetadata.version")}
                placeholder="1.0.0"
              />
            )}
          </Field>

          <Field label="Website" hint="Project page, documentation, or repository landing page.">
            {(bound) => (
              <Input
                {...bound}
                disabled={locked}
                value={website}
                onChange={(event) =>
                  onReeChange((current) =>
                    patchCatalogMetadata(current, { website: event.target.value }),
                  )
                }
                onFocus={() => focus("catalogMetadata.website")}
                placeholder="https://example.org/project"
              />
            )}
          </Field>

          <Field
            label="Description"
            required
            hint="Capture what this REE does, for whom, and any key assumptions."
          >
            {(bound) => (
              <Textarea
                {...bound}
                value={description}
                onChange={(event) =>
                  onReeChange((current) =>
                    patchCatalogMetadata(current, { description: event.target.value }),
                  )
                }
                onFocus={() => focus("catalogMetadata.description")}
                placeholder="REE for reproducible execution of..."
                disabled={locked}
              />
            )}
          </Field>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionLabel}>Keywords</div>
          <div className={styles.chipRow}>
            {keywords.map((keyword) => (
              <span key={keyword} className={styles.chipWrap}>
                <MetadataChip>{keyword}</MetadataChip>
                {!locked && (
                  <button
                    type="button"
                    onClick={() => removeKeyword(keyword)}
                    className={styles.chipRemove}
                    aria-label={`Remove keyword ${keyword}`}
                  >
                    {Ic.x(12)}
                  </button>
                )}
              </span>
            ))}
          </div>
          {!locked && (
            <div className={styles.keywordControls}>
              <div className={styles.keywordRow}>
                <Input
                  aria-label="Custom keyword"
                  value={pendingKeyword}
                  onChange={(event) => setPendingKeyword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addKeyword(pendingKeyword);
                    }
                  }}
                  placeholder="Add custom keyword"
                  density="compact"
                />
                <Button size="small" onClick={() => addKeyword(pendingKeyword)}>
                  Add keyword
                </Button>
              </div>
              {availableSuggestions.length > 0 && (
                <div className={styles.suggestions}>
                  {availableSuggestions.map((keyword) => (
                    <button
                      key={keyword}
                      type="button"
                      onClick={() => addKeyword(keyword)}
                      className={styles.suggestion}
                    >
                      + {keyword}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {locked && <div className={styles.helper}>Unlock fields to add or remove keywords.</div>}
          {keywords.length === 0 && (
            <div className={styles.helper}>
              No keywords yet. Add at least one for discoverability.
            </div>
          )}
        </div>

        <div className={styles.section}>
          <div className={styles.sectionLabel}>Contributors</div>

          {contributors.length > 0 && (
            <div className={styles.contributorList}>
              {contributors.map((contributor) => (
                <div key={`${contributor.identifier}-detail`} className={styles.contributorCard}>
                  <div className={styles.contributorHeader}>
                    <strong className={styles.contributorName}>{contributor.name}</strong>
                    {correspondingAuthor === contributor.identifier && (
                      <Badge tone="success" icon={Ic.check(11)}>
                        Corresponding
                      </Badge>
                    )}
                  </div>
                  {editingContributorId === contributor.identifier ? (
                    <div className={styles.contributorFields}>
                      <Field
                        label="Contributor identifier"
                        required
                        error={contributorFieldError("edit", "identifier")}
                      >
                        {(bound) => (
                          <Input
                            {...bound}
                            value={contributorDraft.identifier}
                            onChange={(event) =>
                              setContributorDraft((prev) => ({
                                ...prev,
                                identifier: event.target.value,
                              }))
                            }
                            placeholder="Identifier"
                            density="compact"
                          />
                        )}
                      </Field>
                      <Field
                        label="Contributor name"
                        required
                        error={contributorFieldError("edit", "name")}
                      >
                        {(bound) => (
                          <Input
                            {...bound}
                            value={contributorDraft.name}
                            onChange={(event) =>
                              setContributorDraft((prev) => ({
                                ...prev,
                                name: event.target.value,
                              }))
                            }
                            placeholder="Name"
                            density="compact"
                          />
                        )}
                      </Field>
                      <Field label="Affiliation name">
                        {(bound) => (
                          <Input
                            {...bound}
                            value={contributorDraft.affiliationName}
                            onChange={(event) =>
                              setContributorDraft((prev) => ({
                                ...prev,
                                affiliationName: event.target.value,
                              }))
                            }
                            placeholder="Affiliation name"
                            density="compact"
                          />
                        )}
                      </Field>
                      <Field label="Affiliation identifier">
                        {(bound) => (
                          <Input
                            {...bound}
                            value={contributorDraft.affiliationIdentifier}
                            onChange={(event) =>
                              setContributorDraft((prev) => ({
                                ...prev,
                                affiliationIdentifier: event.target.value,
                              }))
                            }
                            placeholder="Affiliation identifier"
                            density="compact"
                          />
                        )}
                      </Field>
                    </div>
                  ) : (
                    <div className={styles.contributorFields}>
                      <div className={styles.helper}>
                        <strong className={styles.factLabel}>Identifier:</strong>{" "}
                        {contributor.identifier}
                      </div>
                      <div className={styles.helper}>
                        <strong className={styles.factLabel}>Name:</strong> {contributor.name}
                      </div>
                      <div className={styles.helper}>
                        <strong className={styles.factLabel}>Affiliation Name:</strong>{" "}
                        {contributor.affiliationName || "Not set"}
                      </div>
                      <div className={styles.helper}>
                        <strong className={styles.factLabel}>Affiliation Identifier:</strong>{" "}
                        {contributor.affiliationIdentifier || "Not set"}
                      </div>
                    </div>
                  )}
                  <div className={styles.contributorActions}>
                    {editingContributorId === contributor.identifier ? (
                      <>
                        <Button
                          variant="primary"
                          size="tiny"
                          onClick={saveContributor}
                          aria-label={`Save contributor ${contributor.name}`}
                          title="Save"
                        >
                          {Ic.check(14)}
                        </Button>
                        <Button
                          size="tiny"
                          onClick={cancelContributorEdit}
                          aria-label={`Cancel editing contributor ${contributor.name}`}
                          title="Cancel"
                        >
                          {Ic.x(14)}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="primary"
                          size="tiny"
                          disabled={locked}
                          onClick={() => editContributor(contributor)}
                          aria-label={`Edit contributor ${contributor.name}`}
                          title="Edit"
                        >
                          {Ic.pen(14)}
                        </Button>
                        <Button
                          variant="danger"
                          size="tiny"
                          disabled={locked}
                          onClick={() => removeContributor(contributor.identifier)}
                          aria-label={`Remove contributor ${contributor.name}`}
                          title="Remove"
                        >
                          {Ic.x(14)}
                        </Button>
                        <Button
                          size="tiny"
                          disabled={locked || correspondingAuthor === contributor.identifier}
                          onClick={() =>
                            onReeChange((current) =>
                              setCorrespondingCatalogContributor(current, contributor.identifier),
                            )
                          }
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
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {!locked && (
            <div className={styles.contributorAddFields}>
              <Field
                label="Contributor identifier"
                required
                error={contributorFieldError("add", "identifier")}
              >
                {(bound) => (
                  <Input
                    {...bound}
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
                    density="compact"
                  />
                )}
              </Field>
              <Field label="Contributor name" required error={contributorFieldError("add", "name")}>
                {(bound) => (
                  <Input
                    {...bound}
                    value={pendingContributor.name}
                    onChange={(event) =>
                      setPendingContributor((prev) => ({ ...prev, name: event.target.value }))
                    }
                    placeholder="Name *"
                    density="compact"
                  />
                )}
              </Field>
              <Field label="Affiliation name">
                {(bound) => (
                  <Input
                    {...bound}
                    value={pendingContributor.affiliationName}
                    onChange={(event) =>
                      setPendingContributor((prev) => ({
                        ...prev,
                        affiliationName: event.target.value,
                      }))
                    }
                    placeholder="Affiliation name"
                    density="compact"
                  />
                )}
              </Field>
              <Field label="Affiliation identifier">
                {(bound) => (
                  <Input
                    {...bound}
                    value={pendingContributor.affiliationIdentifier}
                    onChange={(event) =>
                      setPendingContributor((prev) => ({
                        ...prev,
                        affiliationIdentifier: event.target.value,
                      }))
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        addContributor();
                      }
                    }}
                    placeholder="Affiliation identifier"
                    density="compact"
                  />
                )}
              </Field>
            </div>
          )}
          {!locked && (
            <div className={styles.addAction}>
              <Button size="small" onClick={addContributor}>
                Add contributor entity
              </Button>
            </div>
          )}
          {contributors.length === 0 && <div className={styles.helper}>No contributors yet.</div>}
        </div>
      </div>
    </GlassPageShell>
  );
}
