import asyncio
import time
import uuid
import tarfile
import io

from fastapi import HTTPException

from kubernetes import client, config
from kubernetes.stream import stream


# Attempt to load kube config at import time; tests may set KUBECONFIG env var
try:
    config.load_kube_config()
except Exception as e:
    # Don't fail import; callers will deal with connectivity issues.
    print(f"Warning: could not load kubeconfig: {e}")


async def spawn_vm(script_image: str = "alpine", initial_command: list | None = None):
    v1 = client.CoreV1Api()

    session_id = f"ree-{uuid.uuid4().hex[:8]}"

    metadata = client.V1ObjectMeta(name=session_id, labels={"app": "ree-service"})

    # If no initial_command is provided the pod will sleep so we can copy files and exec into it
    if initial_command is None:
        container_command = ["sleep", "3600"]
    else:
        container_command = initial_command

    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        containers=[
            client.V1Container(
                name="research-executor",
                image=script_image,
                command=container_command,
                resources=client.V1ResourceRequirements(
                    limits={"cpu": "1", "memory": "512Mi"}
                ),
            )
        ],
    )

    pod = client.V1Pod(metadata=metadata, spec=pod_spec)

    try:
        v1.create_namespaced_pod(namespace="default", body=pod)
        return {"pod_name": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_pod_results(pod_name: str, timeout: int = 60):
    v1 = client.CoreV1Api()

    start_time = time.time()
    while True:
        pod = v1.read_namespaced_pod_status(name=pod_name, namespace="default")
        if pod.status.phase in ["Succeeded", "Failed"]:
            break
        if time.time() - start_time > timeout:
            raise HTTPException(status_code=408, detail="Research timeout reached")
        time.sleep(2)

    try:
        terminal_output = v1.read_namespaced_pod_log(name=pod_name, namespace="default")
        return {
            "pod_name": pod_name,
            "exit_code": pod.status.container_statuses[0].state.terminated.exit_code,
            "output": terminal_output,
        }
    except Exception as e:
        return {"error": f"Could not fetch logs: {str(e)}"}


def copy_file_to_pod(pod_name: str, namespace: str, local_path: str, remote_path: str):
    """Copy a local file or directory into the pod at the given remote path.

    Streams a tar archive to the pod's `tar -x` stdin using the kubernetes stream websocket.
    """
    api_instance = client.CoreV1Api()

    exec_command = ["tar", "xvf", "-", "-C", "/"]

    try:
        tar_bytes = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode="w") as tar:
            arcname = remote_path.lstrip("/")
            tar.add(local_path, arcname=arcname)

        tar_bytes.seek(0)

        resp = stream(
            api_instance.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            stderr=True,
            stdin=True,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        data = tar_bytes.read()
        # write_stdin expects str; decode bytes preserving values
        resp.write_stdin(data.decode("latin-1"))
        resp.update(timeout=1)
        resp.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy file to pod: {e}")

    return True


def exec_in_pod(
    pod_name: str, namespace: str, command: list[str], timeout: int = 60
) -> str:
    api_instance = client.CoreV1Api()

    try:
        resp = stream(
            api_instance.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=True,
        )
        return resp
    except Exception as e:
        return f"ERROR: {e}"


def create_pod_and_copy_file(
    local_path: str,
    remote_path: str,
    image: str = "alpine",
    namespace: str = "default",
    timeout: int = 30,
) -> str:
    """
    Create a pod, wait for it to be running, and copy a file to it at remote_path.
    Returns the pod name.
    """
    v1 = client.CoreV1Api()
    pod_name = f"copytest-{uuid.uuid4().hex[:8]}"
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name=pod_name, labels={"app": "ree-copy-test"}),
        spec=client.V1PodSpec(
            restart_policy="Never",
            containers=[
                client.V1Container(
                    name="test",
                    image=image,
                    command=["sleep", "60"],
                )
            ],
        ),
    )
    # Create pod
    v1.create_namespaced_pod(namespace=namespace, body=pod)
    # Wait for pod to be running
    start = time.time()
    while time.time() - start < timeout:
        p = v1.read_namespaced_pod_status(pod_name, namespace=namespace)
        if (
            p.status.phase == "Running"
            and p.status.container_statuses
            and p.status.container_statuses[0].ready
        ):
            break
        if p.status.phase in ("Failed", "Succeeded"):
            raise RuntimeError(f"Pod entered terminal phase: {p.status.phase}")
        time.sleep(1)
    else:
        raise TimeoutError("Pod did not become ready in time")
    # Copy file
    copy_file_to_pod(pod_name, namespace, local_path, remote_path)
    return pod_name


if __name__ == "__main__":
    result = asyncio.run(spawn_vm())
    print(result)
    pod_name = result["pod_name"]
    pod_results = get_pod_results(pod_name)
    print(pod_results)
