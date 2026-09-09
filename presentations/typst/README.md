# Typst presentations

Each deck has its own directory beneath this one. Shared visual primitives live
in [`theme/repo2ree.typ`](theme/repo2ree.typ).

## Build

Enter the repository development shell, then run:

```sh
just build-presentations
```

The build writes the starter deck to
`dist/presentations/repo2ree-overview.pdf`.

During editing, rebuild whenever a source or referenced asset changes:

```sh
just watch-typst-overview
```

Typst runs with the repository root as its project root. A deck can therefore
reuse committed documentation assets instead of copying them. Keep deck-local
figures in that deck's `assets/` directory, shared presentation assets under
`assets/`, and shared styling under `theme/`.

## Add a deck

1. Copy `repo2ree-overview/` to a descriptive directory.
2. Keep its entry point named `slides.typ`.
3. Add an explicit build target in `just/presentations.just` so the aggregate
   build remains deterministic and discoverable.
4. Write generated PDFs only to `dist/presentations/`.
