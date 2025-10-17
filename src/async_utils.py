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

logger = logging.getLogger(__name__)


async def launch_workers(worker_tasks: list[partial], done_queue: asyncio.Queue[TaskResult], intermediate_delay: float,
                         max_in_flight: int = 0) -> None:

    sem = asyncio.Semaphore(max_in_flight) if max_in_flight > 0 else None

    for worker in worker_tasks:
        if sem is not None:
            await sem.acquire()

        # worker.args has (nodes, sender, receiver)
        logger.debug(f"Launching task {worker.func.__name__}: {worker.args[1:]}")
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
                                     results_queue: asyncio.Queue[CollectedItem],
                                     total_tasks: int, finished_evt: asyncio.Event):
    for _ in range(total_tasks):
        status, payload = await done_queue.get()
        if status == "ok":
            partial_object, results = payload
            logger.debug(f"Task completed: {partial_object.func.__name__} {partial_object.args[1:]}")
            results_queue.put_nowait((partial_object.func.__name__, results))
        else:
            e, tb = payload  # from the launcher callback
            logger.error(f"Task failed: {e}\n{tb}", e, tb)

    logger.debug("Event is finished")
    finished_evt.set()


async def function_on_queue_item(queue: asyncio.Queue[CollectedItem], async_func: Callable,
                            results: asyncio.Queue[Any]) -> None:
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break
        result = await async_func(item)
        results.put_nowait(result)
        queue.task_done()


async def cleanup_queue_on_event(finished_evt: asyncio.Event, queue: asyncio.Queue, consumers: int = 1):
    await finished_evt.wait()
    logger.debug("Event triggered. Waiting for queue to be finished.")
    await queue.join()
    logger.debug("Queue finished.")

    for _ in range(consumers):
        queue.put_nowait(None)
