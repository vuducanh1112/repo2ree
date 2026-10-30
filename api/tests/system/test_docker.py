"""The same lifecycle on a bench with its own Docker daemon: the product's default bench.

The runtime is an image the bench's daemon builds FROM scratch, so the build runs real
BuildKit steps on the nested daemon while pulling and downloading nothing.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable

from system_client import BUILD_SCRIPT, INSTANT_DOCKER, RESULT, Api

FIXTURE = INSTANT_DOCKER

# A build whose RUN step fails inside the bench's daemon, as a project's own would.
FAILING_DOCKER_BUILD = f"""#!/usr/bin/env sh
set -eu
CONTEXT=$(mktemp -d)
cp /bin/busybox "$CONTEXT/busybox"
cp /lib/ld-musl-*.so.1 "$CONTEXT/"
cat > "$CONTEXT/Dockerfile" <<'DOCKERFILE'
FROM scratch
COPY busybox /bin/busybox
COPY ld-musl-* /lib/
RUN ["/bin/busybox", "sh", "-c", "echo step failing >&2; exit 3"]
DOCKERFILE
docker build -t failing-build "$CONTEXT"
docker save failing-build -o {FIXTURE.runtime}
"""


def test_author_seal_and_download_on_a_docker_bench(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree(image=FIXTURE.image)
    api.author(ree_id, FIXTURE)

    audit = api.audit(ree_id)
    for step in ("source", "evaluation", "hardware", "runtime", "test_activation"):
        assert audit[step]["evidence"] == "current", (step, audit[step])
    assert [(item["name"], item["run"]["evidence"]) for item in audit["experiments"]] == [
        (FIXTURE.experiment, "current")
    ]

    assert api.seal(ree_id)["status"] == "succeeded"
    archive = api.keep_archive(ree_id, "sealed")
    assert archive is not None
    entries = zipfile.ZipFile(io.BytesIO(archive.read_bytes())).namelist()
    assert f"ree/results/{FIXTURE.experiment}/{RESULT}" in entries
    assert any(entry.endswith(BUILD_SCRIPT) for entry in entries)


def test_a_failing_docker_build_step_leaves_no_receipt(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree(image=FIXTURE.image)
    api.acquire(ree_id, FIXTURE)
    api.succeed(ree_id, "evaluate")

    failed = api.build(ree_id, FAILING_DOCKER_BUILD, fixture=FIXTURE)
    assert failed["status"] == "failed"
    assert "step failing" in api.logs(ree_id, failed["run_id"])
    assert api.ree(ree_id)["subject"]["receipts"]["build"] is None
    assert api.audit(ree_id)["runtime"]["evidence"] == "missing"

    # The author's own recipe then builds on the same bench.
    assert api.build(ree_id, fixture=FIXTURE)["status"] == "succeeded"
    assert api.audit(ree_id)["runtime"]["evidence"] == "current"


def test_reviewer_reproduces_a_sealed_docker_ree(api: Api, new_ree: Callable[..., str]) -> None:
    author = new_ree("docker-review-author", image=FIXTURE.image)
    api.author(author, FIXTURE)
    assert api.seal(author)["status"] == "succeeded"
    archive = api.keep_archive(author, "docker-review-baseline")
    assert archive is not None
    data = archive.read_bytes()

    reviewer = new_ree("docker-reviewer", image=FIXTURE.image)
    upload = api.post(
        f"/api/v1/rees/{reviewer}/ree:upload-init",
        {"file_name": "ree.zip", "size": len(data), "content_type": "application/zip"},
    )
    api.request("PUT", upload["upload_url"], content=data)
    api.succeed(reviewer, "ree:load", {"upload_token": upload["upload_token"], "archive_name": "ree.zip"})

    source = api.stage(reviewer, "reviews/source:reproduce", {"basis": "auto"})
    assert source["status"] == "succeeded", api.logs(reviewer, source["run_id"])
    review_id = api.get(f"/api/v1/rees/{reviewer}/reviews")["reviews"][0]["review_id"]

    for stage in ("build:reproduce", "activation:reproduce", f"experiments/{FIXTURE.experiment}:reproduce"):
        payload = {"basis": "auto"} if stage == "build:reproduce" else {}
        run = api.stage(reviewer, f"reviews/{review_id}/{stage}", payload)
        assert run["status"] == "succeeded", (stage, api.logs(reviewer, run["run_id"]))
