import type { DependencyGroup } from "@core/evaluate/dependencyPresentation";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DependencyGroupCard } from "./DependencyGroupCard";

const group: DependencyGroup = {
  path: "requirements.txt",
  ecosystem: "pypi",
  packages: [
    {
      name: "locked-package",
      version: "1.0",
      status: "locked",
      scope: "runtime",
      runtimePresence: "observed",
      observedVersion: "1.0",
    },
    {
      name: "mismatch-package",
      version: "^2",
      status: "pinned",
      scope: null,
      runtimePresence: "version-mismatch",
      observedVersion: "3.0",
    },
    {
      name: "missing-version",
      version: null,
      status: "unpinned",
      scope: null,
      runtimePresence: "not-observed",
      observedVersion: null,
    },
  ],
};

describe("DependencyGroupCard", () => {
  it("renders all package details and toggles an open group", () => {
    const onToggle = vi.fn();
    render(<DependencyGroupCard group={group} filter="all" isOpen onToggle={onToggle} />);

    expect(screen.getByText("2✓")).toBeInTheDocument();
    expect(screen.getByText("1✗")).toBeInTheDocument();
    expect(screen.getByText("runtime")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("version mismatch")).toHaveAttribute("title", "runtime has 3.0");
    expect(screen.getByText("not in runtime")).not.toHaveAttribute("title");
    fireEvent.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("renders a closed group without package rows", () => {
    render(<DependencyGroupCard group={group} filter="all" isOpen={false} onToggle={vi.fn()} />);
    expect(screen.getByText("requirements.txt")).toBeInTheDocument();
    expect(screen.queryByText("locked-package")).not.toBeInTheDocument();
  });

  it("filters rows by status", () => {
    render(<DependencyGroupCard group={group} filter="locked" isOpen onToggle={vi.fn()} />);
    expect(screen.getByText("locked-package")).toBeInTheDocument();
    expect(screen.queryByText("mismatch-package")).not.toBeInTheDocument();
  });

  it("omits a group with no packages matching the active filter", () => {
    const { container } = render(
      <DependencyGroupCard group={group} filter="ranged" isOpen onToggle={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("omits the unresolved tally when every package is resolved", () => {
    render(
      <DependencyGroupCard
        group={{ ...group, packages: group.packages.slice(0, 2) }}
        filter="all"
        isOpen
        onToggle={vi.fn()}
      />,
    );
    expect(screen.queryByText(/✗/)).not.toBeInTheDocument();
  });
});
