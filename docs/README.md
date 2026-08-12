# repo2ree documentation

Documentation is organized first by audience, then by the kind of help a reader
needs. This keeps public product guidance separate from contributor operations
while applying the Diátaxis distinction inside each audience.

## Public documentation

- [Public docs](public/README.md)
  - [Tutorials](public/tutorials/README.md) teach through a complete guided
    experience.
  - [How-to guides](public/README.md#how-to-guides) help authors and reviewers complete a goal.
  - [Reference](public/README.md#reference) defines concepts and current capabilities.
  - [Explanation](public/README.md#explanation) develops the product's purpose and mental
    model.

## Engineering documentation

- [Engineering docs](engineering/README.md)
  - **Tutorials** will provide guided contributor learning when the project has
    material distinct from setup procedures.
  - [How-to guides](engineering/README.md#how-to-guides) cover development, testing, and
    deployment tasks.
  - [Explanations](engineering/README.md#explanation) describe why important mechanisms
    work as they do.
  - [Decision records](engineering/decisions/) preserve consequential choices
    and their tradeoffs.

## Shared reference and research

- [Project reference](reference/README.md) contains the normative concepts and
  current/target architecture shared across audiences.
- [Research notes](research/README.md) support positioning, comparison, and
  manuscript work. They are a research corpus rather than a Diátaxis section.

## Website publication boundary

`make docs-site` publishes only `docs/public/` and assets stored below it. The
generated static site is disposable and lives under `sites/docs/`.

Engineering documentation, architecture decision records, shared design
reference, research notes, and the remaining diagrams stay in the repository.
The end-user website includes them only after a deliberate promotion into the
public tree and `zensical.toml`.
