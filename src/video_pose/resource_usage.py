from __future__ import annotations

import importlib.util
import os
import resource

from pydantic import BaseModel


class ResourceSnapshot(BaseModel):
    rss_mb: float
    gpu_allocated_mb: float | None = None
    gpu_reserved_mb: float | None = None


def _rss_mb() -> float:
    statm = "/proc/self/statm"
    if os.path.exists(statm):
        with open(statm, encoding="utf-8") as handle:
            fields = handle.read().split()
        if len(fields) >= 2:
            pages = int(fields[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            return pages * page_size / (1024.0 * 1024.0)

    usage = resource.getrusage(resource.RUSAGE_SELF)
    value = float(usage.ru_maxrss)
    if os.uname().sysname == "Darwin":
        return value / (1024.0 * 1024.0)
    return value / 1024.0


def sample_process_resources() -> ResourceSnapshot:
    gpu_allocated: float | None = None
    gpu_reserved: float | None = None

    if importlib.util.find_spec("torch") is not None:
        try:
            import torch

            if torch.cuda.is_available():
                gpu_allocated = (
                    torch.cuda.memory_allocated() / (1024.0 * 1024.0)
                )
                gpu_reserved = (
                    torch.cuda.memory_reserved() / (1024.0 * 1024.0)
                )
        except Exception:
            gpu_allocated = None
            gpu_reserved = None

    return ResourceSnapshot(
        rss_mb=_rss_mb(),
        gpu_allocated_mb=gpu_allocated,
        gpu_reserved_mb=gpu_reserved,
    )
