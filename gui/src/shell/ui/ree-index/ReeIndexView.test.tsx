/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../tests/support/renderApp";
import { ReeIndexView } from "./ReeIndexView";

describe("ReeIndexView", () => {
  it("lists sealed REEs, archive links, filtering, refresh, and back navigation", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    const listReeIndex = vi.fn().mockResolvedValue({
      items: [
        {
          subject_digest: "sha256:0123456789abcdef",
          name: "Python hello world",
          sealed_at: "2026-01-01T12:00:00Z",
          catalog_metadata: {},
          ree_version: "1",
          archive_attestations: [
            {
              archive: "zenodo",
              identifier: "10.5281/demo",
              record_url: "https://example.test/record",
            },
          ],
        },
        {
          subject_digest: "sha256:fedcba9876543210",
          name: "Local only",
          sealed_at: "2026-01-02T12:00:00Z",
          catalog_metadata: {},
          ree_version: "1",
          archive_attestations: [],
        },
      ],
      next_cursor: null,
    });
    renderWithShell(<ReeIndexView onBack={onBack} />, {
      services: fakeApiServices({ ree: { listReeIndex } }),
    });

    expect(await screen.findByText("Python hello world")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /10.5281\/demo/ })).toHaveAttribute(
      "href",
      "https://example.test/record",
    );
    expect(screen.getByText("Not deposited")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Deposited only/ }));
    await waitFor(() => expect(listReeIndex).toHaveBeenCalledWith({ depositedOnly: true }));
    await user.click(screen.getByRole("button", { name: /Refresh/ }));
    await user.click(screen.getByRole("button", { name: /Back/ }));
    expect(onBack).toHaveBeenCalledOnce();
  });
});
