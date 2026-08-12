import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Field, Input, Select, Textarea } from "./FormControl";

describe("Field", () => {
  // The association is the whole reason this primitive exists: the hand-rolled
  // label/helper pairs it replaces rendered the text and stopped there, so the
  // control had no accessible name and the hint was never read out.
  it("names its control, so the field is addressable by its label", () => {
    render(
      <Field label="Repository">
        {(bound) => <Input {...bound} defaultValue="github.com/acme/thing" />}
      </Field>,
    );
    expect(screen.getByLabelText("Repository")).toHaveValue("github.com/acme/thing");
  });

  it("wires the hint to the control rather than only displaying it", () => {
    render(
      <Field label="Repository" hint="Local path or URL">
        {(bound) => <Input {...bound} />}
      </Field>,
    );
    expect(screen.getByLabelText("Repository")).toHaveAccessibleDescription("Local path or URL");
  });

  it("describes nothing when there is no hint", () => {
    render(<Field label="Repository">{(bound) => <Input {...bound} />}</Field>);
    expect(screen.getByLabelText("Repository")).not.toHaveAttribute("aria-describedby");
  });

  it("gives each field its own ids, so two on a page do not cross-wire", () => {
    render(
      <>
        <Field label="First">{(bound) => <Input {...bound} />}</Field>
        <Field label="Second">{(bound) => <Input {...bound} />}</Field>
      </>,
    );
    expect(screen.getByLabelText("First").id).not.toBe(screen.getByLabelText("Second").id);
  });
});

describe("controls", () => {
  it("accepts typing and reports it", async () => {
    render(<Input aria-label="Name" />);
    await userEvent.type(screen.getByLabelText("Name"), "acme");
    expect(screen.getByLabelText("Name")).toHaveValue("acme");
  });

  it("refuses input while disabled", async () => {
    render(<Input aria-label="Name" disabled />);
    await userEvent.type(screen.getByLabelText("Name"), "acme");
    expect(screen.getByLabelText("Name")).toHaveValue("");
  });

  it("renders a select with its options addressable", () => {
    render(
      <Select aria-label="Runtime">
        <option value="docker">Docker</option>
        <option value="nix">Nix</option>
      </Select>,
    );
    expect(screen.getByRole("option", { name: "Nix" })).toBeInTheDocument();
  });

  it("switches a textarea to the code skin when asked", () => {
    render(<Textarea aria-label="Run script" flavor="code" />);
    expect(screen.getByLabelText("Run script")).toHaveAttribute("data-flavor", "code");
  });

  it("is prose by default", () => {
    render(<Textarea aria-label="Notes" />);
    expect(screen.getByLabelText("Notes")).toHaveAttribute("data-flavor", "prose");
  });
});
