# API end-to-end walkthrough

The pure-API counterpart of `gui/tests/e2e`: a REE authored end to end over
HTTP, no GUI. It drives only the public, automation-ready surface — the same
calls any automation client (an AI agent included) makes.

It is an **honest** recording, not a staged one. Every API interaction is a real
`curl` subprocess and the command printed to an [asciinema](https://asciinema.org)
recording is the exact one executed — one argv, echoed and run. There is no
fabricated "agent thinking": the narrative is carried by neutral section banners
(the author's chapter headings), not first-person prose pretending to be a model's
inner monologue.

It is **not** a pytest. It drives a *live* backend + workbench-agent stack over
the network, asserts every response, and its stdout is the artifact. Run it
through the stack orchestrator, which brings the stack up, points `API_BASE_URL`
at it, tears it down, and (with `make demo-api`) records the terminal session:

```sh
make demo-api        # bring up the stack, run this, record to a .cast, tear down
# or against an already-running stack:
API_BASE_URL=http://127.0.0.1:8000 api/tests/e2e/api_agent_walkthrough.py
```

`make demo-api` writes `test-artifacts/casts/api-agent-walkthrough.cast` and, because a
recording is a poor standalone document, derives
`test-artifacts/casts/api-agent-walkthrough.md` from it — a chaptered written
transcript (`render_cast_transcript.py`): the walkthrough's section banners
become headings, the `#` asides become prose, and the real commands with their
real responses stay as console blocks. Same artifact, written form — it cannot
drift from the recording. Render the cast to a GIF/SVG with
`agg test-artifacts/casts/api-agent-walkthrough.cast out.gif`.

The Python is pure orchestration — control flow, the `observeRun` poll loop, JSON
parsing, assertions. Needs only `curl` (already required by the stack
orchestrator) and the Python stdlib, so it runs under a bare `python3`.
