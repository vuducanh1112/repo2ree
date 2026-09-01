# repo2ree documentation

Documentation is organized by audience, then by purpose. Public product guidance
stays separate from contributor operations, and each audience follows Diátaxis.

## Public documentation

- [Tutorials](public/tutorials/README.md) provide guided experiences.
- [How-to guides](public/README.md#how-to-guides) help authors and reviewers
  complete a goal.
- [Reference](public/README.md#reference) defines concepts and capabilities.
- [Explanation](public/README.md#explanation) describes the product's purpose
  and mental model.

## Engineering documentation

- [How-to guides](engineering/README.md#how-to-guides) cover development,
  testing, and deployment.
- [Explanations](engineering/README.md#explanation) describe why important
  mechanisms work as they do.
- [Reference](engineering/reference/README.md) defines technical concepts,
  architecture, and package boundaries.
- [Decision records](engineering/decisions/) preserve consequential choices
  and tradeoffs.

## Research

[Research notes](research/README.md) support positioning, comparison, and
manuscript work. They are a research corpus, not a Diátaxis section.

## Website publication boundary

`just docs-site` publishes only `docs/public/` and assets stored below it. The
generated static site is disposable and lives under `sites/docs/`.

Engineering docs, research notes, and unpublished diagrams stay in the
repository. Publishing them requires moving or adapting them under
`docs/public/` and adding them to `zensical.toml`.
