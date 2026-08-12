/// <reference types="vite/client" />
/// <reference types="@vitest/browser-playwright" />

// Ambient types for the assets Vite resolves but TypeScript does not, above all
// `*.module.css`: without this reference every CSS Module import is an
// unresolved module and `styles.foo` is an error.
//
// The provider reference is what fills in `vitest/browser`'s `CDPSession`.
// Vitest ships it as an empty interface and each provider augments it; the
// augmentation lives in the provider's own entry point, which nothing in `src`
// imports — the browser project wires it up in vite.config.js instead.
