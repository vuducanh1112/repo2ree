# repo2ree presentations

Presentation sources live here, separated by authoring system. This structure
lets us add another stack without accidentally sharing dependencies or
conventions.

- [`typst/`](typst/) contains PDF-first decks built with Typst.
- A future Slidev stack should live in `slidev/` with its own package manifest
  and lock file rather than using the GUI's dependencies.

Generated presentations are disposable and belong under
`dist/presentations/`, which Git ignores with the rest of `dist/`.

Use `just build-presentations` to build every deck.
