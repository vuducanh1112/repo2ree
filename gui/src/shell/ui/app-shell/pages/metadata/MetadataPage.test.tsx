import { createEmptyReeSpec, type ReeSpec } from "@core/ree/ReeSpec";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { PageMetadataEntry } from "./MetadataPage";

/**
 * The page is controlled: it owns no spec of its own, it calls `onReeChange`.
 * Rendering it bare would make every edit a no-op, so this harness supplies the
 * state the app shell normally holds — which also means the assertions below
 * exercise the real `catalogMetadataOps` round-trip, not a stub of it.
 */
function renderPage({ locked = false, spec }: { locked?: boolean; spec?: Partial<ReeSpec> } = {}) {
  const seen: ReeSpec[] = [];

  function Harness() {
    const [reeSpec, setReeSpec] = useState<ReeSpec>({ ...createEmptyReeSpec(), ...spec });
    seen.push(reeSpec);
    return (
      <PageMetadataEntry
        reeSpec={reeSpec}
        locked={locked}
        badges={{}}
        focusedField={null}
        onReeChange={setReeSpec}
        onLockedChange={vi.fn()}
        onGoPage={vi.fn()}
        onFocusedFieldChange={vi.fn()}
      />
    );
  }

  render(<Harness />);
  return { current: () => seen[seen.length - 1] };
}

// The placeholders the e2e `provideMetadata` helper fills. Selecting on the same
// strings keeps this test and the browser suite pointed at one set of fields.
const NAME = "deepfold-protein-structure-prediction";
const VERSION = "1.0.0";
const DESCRIPTION = "REE for reproducible execution of...";

describe("PageMetadataEntry", () => {
  describe("identity fields", () => {
    it("reports the name as it is typed", async () => {
      const page = renderPage();

      await userEvent.type(screen.getByPlaceholderText(NAME), "hello-world");

      expect(page.current().name).toBe("hello-world");
    });

    it("writes version and description into the catalog metadata, not the spec root", async () => {
      const page = renderPage();

      await userEvent.type(screen.getByPlaceholderText(VERSION), "2.1.0");
      await userEvent.type(screen.getByPlaceholderText(DESCRIPTION), "A hello world REE");

      expect(page.current().catalogMetadata).toMatchObject({
        version: "2.1.0",
        description: "A hello world REE",
      });
    });

    it("reads Draft until the REE is named, then Ready", async () => {
      renderPage();
      expect(screen.getByText("Draft")).toBeInTheDocument();

      await userEvent.type(screen.getByPlaceholderText(NAME), "hello-world");

      expect(screen.getByText("Ready")).toBeInTheDocument();
    });

    it("does not count whitespace as a name", async () => {
      renderPage();
      await userEvent.type(screen.getByPlaceholderText(NAME), "   ");
      expect(screen.getByText("Draft")).toBeInTheDocument();
    });
  });

  describe("keywords", () => {
    it("adds one from the input", async () => {
      const page = renderPage();

      await userEvent.type(screen.getByPlaceholderText("Add custom keyword"), "genomics");
      await userEvent.click(screen.getByRole("button", { name: "Add keyword" }));

      expect(page.current().catalogMetadata.keywords).toEqual(["genomics"]);
    });

    it("adds one on Enter, without submitting anything", async () => {
      const page = renderPage();

      await userEvent.type(screen.getByPlaceholderText("Add custom keyword"), "hpc{Enter}");

      expect(page.current().catalogMetadata.keywords).toEqual(["hpc"]);
    });

    it("clears the input after adding, so the next keyword starts empty", async () => {
      renderPage();
      const input = screen.getByPlaceholderText("Add custom keyword");

      await userEvent.type(input, "hpc{Enter}");

      expect(input).toHaveValue("");
    });

    it("removes one by name", async () => {
      const spec = createEmptyReeSpec();
      spec.catalogMetadata.keywords = ["genomics", "hpc"];
      const page = renderPage({ spec });

      await userEvent.click(screen.getByRole("button", { name: "Remove keyword genomics" }));

      expect(page.current().catalogMetadata.keywords).toEqual(["hpc"]);
    });
  });

  describe("contributors", () => {
    async function fillContributor(identifier: string, name: string) {
      await userEvent.type(screen.getByPlaceholderText("Identifier"), identifier);
      await userEvent.type(screen.getByPlaceholderText("Name *"), name);
      await userEvent.click(screen.getByRole("button", { name: "Add contributor entity" }));
    }

    it("says so when there are none", () => {
      renderPage();
      expect(screen.getByText("No contributors yet.")).toBeInTheDocument();
    });

    it("adds one and makes the first the corresponding author", async () => {
      const page = renderPage();

      await fillContributor("0000-0002-1825-0097", "Josiah Carberry");

      expect(page.current().catalogMetadata.contributors).toHaveLength(1);
      expect(page.current().catalogMetadata.correspondingAuthorIdentifier).toBe(
        "0000-0002-1825-0097",
      );
      expect(screen.getByText("Corresponding")).toBeInTheDocument();
    });

    it("surfaces the validation error rather than adding a nameless entry", async () => {
      const page = renderPage();

      await userEvent.type(screen.getByPlaceholderText("Identifier"), "0000-0002-1825-0097");
      await userEvent.click(screen.getByRole("button", { name: "Add contributor entity" }));

      expect(screen.getByText("Name is required to add a contributor.")).toBeInTheDocument();
      expect(page.current().catalogMetadata.contributors).toHaveLength(0);
    });

    it("refuses a duplicate identifier", async () => {
      const page = renderPage();

      await fillContributor("0000-0002-1825-0097", "Josiah Carberry");
      await fillContributor("0000-0002-1825-0097", "Someone Else");

      expect(
        screen.getByText("A contributor with this identifier already exists."),
      ).toBeInTheDocument();
      expect(page.current().catalogMetadata.contributors).toHaveLength(1);
    });

    it("clears the draft fields after a successful add", async () => {
      renderPage();

      await fillContributor("0000-0002-1825-0097", "Josiah Carberry");

      expect(screen.getByPlaceholderText("Identifier")).toHaveValue("");
      expect(screen.getByPlaceholderText("Name *")).toHaveValue("");
    });

    it("removes one", async () => {
      const page = renderPage();
      await fillContributor("0000-0002-1825-0097", "Josiah Carberry");

      await userEvent.click(
        screen.getByRole("button", { name: "Remove contributor Josiah Carberry" }),
      );

      expect(page.current().catalogMetadata.contributors).toHaveLength(0);
    });
  });

  describe("when locked", () => {
    const spec = createEmptyReeSpec();
    spec.name = "hello-world";
    spec.catalogMetadata.keywords = ["genomics"];

    it("disables the identity inputs", () => {
      renderPage({ locked: true, spec });
      expect(screen.getByPlaceholderText(NAME)).toBeDisabled();
      expect(screen.getByPlaceholderText(VERSION)).toBeDisabled();
    });

    it("withdraws the editing controls entirely, rather than disabling them", () => {
      // A sealed REE's metadata is evidence; the affordances should not be there
      // to click at all.
      renderPage({ locked: true, spec });
      expect(screen.queryByPlaceholderText("Add custom keyword")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Remove keyword/ })).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Add contributor entity" }),
      ).not.toBeInTheDocument();
    });

    it("still shows the values it will not let you change", () => {
      renderPage({ locked: true, spec });
      expect(screen.getByPlaceholderText(NAME)).toHaveValue("hello-world");
      expect(screen.getByText("genomics")).toBeInTheDocument();
    });
  });
});
