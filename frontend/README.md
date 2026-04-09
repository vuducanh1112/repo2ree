# repo2ree Web UI

Simple Vite + React frontend to browse REEs produced by the backend.

Quick start (from repository root):

1. Start backend fastapi from the repo root dir

```bash
sudo env "PATH=$PATH" uvicorn repo2ree.service.api.main:app --reload
```

2. Install frontend deps

```bash
cd src/repo2ree/web
npm install
```

3. Run (dev server proxied to backend at http://localhost:8000)

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev -- --host
```

The UI fetches REE metadata from `/api/ree` and details from `/api/ree/:id`.
