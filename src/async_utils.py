# Python Imports
import asyncio
import logging
import traceback
from functools import partial
from typing import List, Tuple

# Project Imports


logger = logging.getLogger(__name__)
# [(node_sender, {node_receiver: (timestamp, message)}), ...]
RequestResult = Tuple[str, dict[str, Tuple[int, str]]]


async def launch_workers(worker_tasks: List[partial], done_queue: asyncio.Queue[tuple[str, object]], intermediate_delay: float,
                         max_in_flight: int = 0) -> None:

    sem = asyncio.Semaphore(max_in_flight) if max_in_flight > 0 else None

    for worker in worker_tasks:
        if sem is not None:
            await sem.acquire()

        # worker.args has (nodes, sender, receiver)
        logger.info(f"Launching task {worker.func.__name__}: {worker.args[1:]}")
        fut = asyncio.create_task(worker())

        def _on_done(t: asyncio.Task, j=worker) -> None:
            if sem is not None:
                sem.release()
            try:
                result = t.result()
                done_queue.put_nowait(("ok", (j.func.__name__, j.args[1:], result)))
            except Exception as e:
                tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                done_queue.put_nowait(("err", (e, tb)))

        fut.add_done_callback(_on_done)

        if intermediate_delay:
            await asyncio.sleep(intermediate_delay)


async def collect_results(done_q: asyncio.Queue[tuple[str, object]], total_tasks: int) -> List[RequestResult]:
    collected: List[RequestResult] = []
    for _ in range(total_tasks):
        status, payload = await done_q.get()
        if status == "ok":
            func_name, args, results = payload
            logger.info(f"Task completed: {func_name} {args}")
            collected.append(results)
        else:
            e, tb = payload  # from the launcher callback
            logger.error(f"Task failed: {e}\n{tb}", e, tb)

    return collected
