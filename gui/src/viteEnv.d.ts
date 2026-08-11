/// <reference types="vite/client" />

// Ambient types for the assets Vite resolves but TypeScript does not, above all
// `*.module.css`: without this reference every CSS Module import is an
// unresolved module and `styles.foo` is an error.
