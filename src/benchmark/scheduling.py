"""Bounded spawned workers with process-group cleanup on interruption or failure."""

import multiprocessing as mp
import os
import queue
import signal
import traceback


def _worker(tasks, results, continue_on_error=False):
    if os.name != "nt":
        os.setsid()
    from .cli import execute

    while True:
        item = tasks.get()
        if item is None:
            return
        index, task = item
        try:
            results.put((index, execute(task), None))
        except BaseException:
            results.put((index, None, traceback.format_exc()))
            if not continue_on_error:
                return


def run_tasks(tasks, workers=4, continue_on_error=False):
    """Execute cases in stable input order with at most four managed simulators."""
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("Worker count must be 1–4")
    if not tasks:
        return []
    context = mp.get_context("spawn")
    pending = context.Queue()
    returned = context.Queue()
    processes = [
        context.Process(target=_worker, args=(pending, returned, continue_on_error))
        for _ in range(min(workers, len(tasks)))
    ]
    output = {}
    try:
        for process in processes:
            process.start()
        for index, task in enumerate(tasks):
            pending.put((index, task))
        for _ in processes:
            pending.put(None)
        while len(output) < len(tasks):
            try:
                index, value, error = returned.get(timeout=0.5)
            except queue.Empty:
                failed = [p for p in processes if p.exitcode not in (None, 0)]
                if failed or not any(p.is_alive() for p in processes):
                    raise RuntimeError("A benchmark worker exited before returning every result")
                continue
            if error:
                if not continue_on_error:
                    raise RuntimeError(error)
            output[index] = value
        for process in processes:
            process.join(timeout=5)
        return [output[index] for index in range(len(tasks))]
    finally:
        for process in processes:
            if process.pid is None:
                continue
            if process.is_alive() or process.exitcode not in (None, 0):
                if os.name != "nt":
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join()
        pending.cancel_join_thread()
        pending.close()
        returned.close()
