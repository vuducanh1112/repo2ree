# Observability backends

Local collector stacks for traces, metrics, and logs. The application only
speaks OTLP to `OTLP_ENDPOINT` (HTTP on `4318`), so every backend here is a
drop-in swap — start one, point the stack at it, done. They cannot run
side by side without remapping ports (all bind `4317/4318`), and each keeps
its telemetry in its own volume, so history does not carry across a switch.

```sh
docker compose -f observability/docker-compose.<backend>.yml up -d

OTLP_ENDPOINT=http://host.docker.internal:4318 just demo-gui-stack-local
# (host.docker.internal resolves inside the compose services via host-gateway;
#  processes running directly on the host use http://localhost:4318)
```

| Backend | UI | Logs stored | Notes |
| --- | --- | --- | --- |
| [ClickStack](docker-compose.clickstack.yml) | :8080 | yes | ClickHouse + HyperDX. Trace ↔ logs correlation, SQL over span attributes. **Ingest is authenticated** — see below. |
| [Grafana LGTM](docker-compose.lgtm.yml) | :3000 | yes | Tempo/Loki/Mimir/Grafana in one container (admin/admin). Trace → logs via span links. |
| [Jaeger](docker-compose.jaeger.yml) | :16686 | no | Traces only — the original minimal setup. |

All three are dev/demo images by their vendors' own positioning; that matches
what this directory is for.

## ClickStack ingestion key

Unlike the others, open-source ClickStack rejects OTLP requests without an
`authorization` header. Copy the **Ingestion API Key** from the HyperDX UI
(Team Settings → API Keys) and pass it via the standard OTLP env var, which
the SDK exporters and the executor span relay both honor, and which the
control-plane/agent compose files pass through:

```sh
OTLP_ENDPOINT=http://host.docker.internal:4318 \
OTEL_EXPORTER_OTLP_HEADERS="authorization=<ingestion-key>" \
just demo-gui-stack-local
```

## What lands where

- **Traces**: every API request, background run (`run.*`), dispatch, and —
  relayed from inside the workbench container — the executor's `command.*` /
  `process.exec` spans, wide-event attributes included (args, receipts,
  exit codes, output tails on failure).
- **Logs**: host process logs (API, agent) plus the full workbench run
  stream (`repo2ree.run` logger), each line trace-correlated and tagged with
  `repo2ree.ree_id` / `repo2ree.run_id` / `repo2ree.stream` — durable past
  container teardown, unlike `docker logs`.
- **Metrics**: the `workbench.*` / `agent.*` counters and duration
  histograms.

Without a collector, spans fall back to `TRACE_FILE` (NDJSON) or stdout; logs
fall back to stdout only.
