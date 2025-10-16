# Python Imports
import asyncio
import logging
import traceback
from collections.abc import Callable
from functools import partial
from typing import Literal, Any

# Project Imports
from src.dataclasses import ResultEntry


RequestResult = tuple[partial, ResultEntry]
RequestError  = tuple[Exception, str]

TaskOk  = tuple[Literal["ok"], RequestResult]
TaskErr = tuple[Literal["err"], RequestError]
TaskResult = TaskOk | TaskErr

CollectedItem = tuple[str, ResultEntry]

SENTINEL: TaskResult | None = None  # stop signal for collectors

logger = logging.getLogger(__name__)


async def launch_workers(worker_tasks: list[partial], done_queue: asyncio.Queue[TaskResult], intermediate_delay: float,
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
                done_queue.put_nowait(("ok", (j, result)))
            except Exception as e:
                tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                done_queue.put_nowait(("err", (e, tb)))

        fut.add_done_callback(_on_done)

        if intermediate_delay:
            await asyncio.sleep(intermediate_delay)


async def collect_results_from_tasks(done_queue: asyncio.Queue[TaskResult | None],
                                     results_queue: asyncio.Queue[CollectedItem | None]):
    while True:
        item = await done_queue.get()
        if item is SENTINEL:
            logger.info(f"Consumer finished.")
            results_queue.put_nowait(SENTINEL)
            break
        status, payload = item
        if status == "ok":
            partial_object, results = payload
            logger.info(f"Task completed: {partial_object.func.__name__} {partial_object.args[1:]}")
            results_queue.put_nowait((partial_object.func.__name__, results))
        else:
            e, tb = payload  # from the launcher callback
            logger.error(f"Task failed: {e}\n{tb}", e, tb)


async def signal_when_done(launcher_task: asyncio.Task,
                            done_queue: asyncio.Queue[TaskResult | None],
                            num_collectors: int) -> None:
    try:
        await launcher_task
    finally:
        # Always signal collectors to stop, even if launcher errored/cancelled
        for _ in range(num_collectors):
            await done_queue.put(None)


async def function_on_queue_item(queue: asyncio.Queue[CollectedItem], async_func: Callable,
                            results: asyncio.Queue[Any]) -> None:
    while True:
        item = await queue.get()
        if item is SENTINEL:
            break
        result = await async_func(item)
        results.put_nowait(result)