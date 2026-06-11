from __future__ import annotations

import platform

from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.hbom.cpu_profiler import profile_cpus
from repo2ree_core.hbom.gpu_profiler import profile_gpus
from repo2ree_core.hbom.memory_profiler import profile_memory
from repo2ree_core.hbom.network_profiler import profile_network
from repo2ree_core.hbom.storage_profiler import profile_storage
from repo2ree_protocol.tracing import get_tracer

tracer = get_tracer(__name__)


def generate_hbom() -> HBOM:
    with tracer.start_as_current_span("hbom.profile_cpu"):
        cpus = profile_cpus()
    with tracer.start_as_current_span("hbom.profile_gpu"):
        gpus = profile_gpus()
    with tracer.start_as_current_span("hbom.profile_memory"):
        memory = profile_memory()
    with tracer.start_as_current_span("hbom.profile_storage"):
        storage = profile_storage()
    with tracer.start_as_current_span("hbom.profile_network"):
        network = profile_network()

    return HBOM(
        cpus=cpus,
        gpus=gpus,
        memory=memory,
        storage=storage,
        network=network,
        extra_info={
            "profiled_on": platform.node(),
            "platform_system": platform.system(),
            "platform_release": platform.release(),
        },
    )
