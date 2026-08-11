# repo2ree Web UI

Simple Vite + React GUI for the repo2ree API.

## Engineering docs

Current setup, deployment, and test commands live in the repo-level engineering
docs:

- [Development setup](../docs/engineering/how-to/development.md)
- [Deployment notes](../docs/engineering/how-to/deployment.md)
- [Testing guide](../docs/engineering/how-to/testing.md)

## Local GUI loop

```bash
npm --prefix gui ci
VITE_API_BASE_URL=http://localhost:8000 npm --prefix gui run dev -- --host
```
