# repo2ree Web UI

Simple Vite + React frontend for the repo2ree API.

## Engineering docs

Current setup, deployment, and test commands live in the repo-level engineering
docs:

- [Development setup](../docs/engineering/development.md)
- [Deployment notes](../docs/engineering/deployment.md)
- [Testing guide](../docs/engineering/testing.md)

## Local frontend loop

```bash
npm --prefix frontend ci
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --host
```
