from __future__ import annotations

import platform

from repo2ree_core.hbom.cpu_profiler import profile_cpus
from repo2ree_core.hbom.gpu_profiler import profile_gpus
from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.hbom.memory_profiler import profile_memory
from repo2ree_core.hbom.network_profiler import profile_network
from repo2ree_core.hbom.storage_profiler import profile_storage


def generate_hbom() -> HBOM:
    return HBOM(
        cpus=profile_cpus(),
        gpus=profile_gpus(),
        memory=profile_memory(),
        storage=profile_storage(),
        network=profile_network(),
        extra_info={
            "profiled_on": platform.node(),
            "platform_system": platform.system(),
            "platform_release": platform.release(),
        },
    )
