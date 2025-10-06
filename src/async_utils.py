# Python Imports
import logging
import asyncio
from typing import Iterable, List, Tuple, Dict, Optional

# Project Imports
from src.status_backend import StatusBackend


logger = logging.getLogger(__name__)


def make_jobs(senders: Iterable[str], receivers: Iterable[str]) -> List[Tuple[str, str]]:
    """Cartesian product of senders x receivers."""
    return [(s, r) for s in senders for r in receivers]


async def enqueue_jobs(job_q: asyncio.Queue[Optional[Tuple[str, str]]],
                       jobs: List[Tuple[str, str]]) -> None:
    for job in jobs:
        logger.info(f"Enqueued job: {job}")
        await job_q.put(job)
    logger.info("Adding none, no more jobs")
    await job_q.put(None)


async def launch_workers(nodes: Dict[str, StatusBackend],
                         job_q: asyncio.Queue[Optional[Tuple[str, str]]],
                         done_q: asyncio.Queue[Optional[asyncio.Task]],
                         intermediate_delay: float,
                         max_in_flight: int = 0,
                         func = None) -> None:

    sem = asyncio.Semaphore(max_in_flight) if max_in_flight > 0 else None

    while True:
        item = await job_q.get()
        if item is None:
            logger.info("No more jobs, exiting launcher")
            break

        sender, receiver = item

        if sem is not None:
            await sem.acquire()

        logger.info(f"Launching job {func.__name__}: {sender} -> {receiver}")
        fut = asyncio.create_task(func(nodes, sender, receiver))
        # TODO correctly attach metadata for logging/errors
        fut._sender_receiver = (sender, receiver)  # type: ignore[attr-defined]

        def _on_done(t: asyncio.Task) -> None:
            # release concurrency slot (if any), then notify collector
            if sem is not None:
                sem.release()
            done_q.put_nowait(t)

        fut.add_done_callback(_on_done)

        await asyncio.sleep(intermediate_delay)

    logger.info("Adding None, no more workers")
    await done_q.put(None)


async def collect_results(done_q: asyncio.Queue[asyncio.Task | None], function: str = None) -> List:
    """Collect results from `done_q` until `done_q` yields `None`."""
    results: List = []
    while True:
        fut = await done_q.get()
        if fut is None:
            logger.info(f"No more results to collect from {function}")
            break
        try:
            result = await fut
            logger.info(f"Collected result from {function}")
            results.append(result)
        except Exception as e:
            logger.error(f"Error collecting result from {function}: {e!r}")

    return results
