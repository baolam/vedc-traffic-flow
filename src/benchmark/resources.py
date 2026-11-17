"""Host-local simulator leases shared across training and evaluation processes."""

import getpass
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def _try_lock(handle):
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle):
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def simulator_slot(limit=4, timeout=120):
    """Hold one of at most four machine-local simulator slots until shutdown."""
    if type(limit) is not int or not 1 <= limit <= 4:
        raise ValueError("SUMO worker limit must be between one and four")
    user = str(os.getuid()) if hasattr(os, "getuid") else getpass.getuser()
    directory = Path(tempfile.gettempdir()) / f"edgeflow-sumo-{user}"
    directory.mkdir(mode=0o700, exist_ok=True)
    deadline = time.monotonic() + timeout
    lease = None
    try:
        while lease is None:
            for index in range(limit):
                handle = (directory / f"{index}.lock").open("a+")
                if handle.tell() == 0:
                    handle.write("0")
                    handle.flush()
                try:
                    _try_lock(handle)
                    lease = handle
                    break
                except OSError:
                    handle.close()
            if lease is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("No free SUMO process slot")
                time.sleep(0.05)
        yield
    finally:
        if lease:
            _unlock(lease)
            lease.close()


@contextmanager
def coordinator():
    """Reject overlapping managed campaigns instead of multiplying worker pools."""
    user = str(os.getuid()) if hasattr(os, "getuid") else getpass.getuser()
    path = Path(tempfile.gettempdir()) / f"edgeflow-coordinator-{user}.lock"
    with path.open("a+") as handle:
        if handle.tell() == 0:
            handle.write("0")
            handle.flush()
        try:
            _try_lock(handle)
        except OSError as error:
            raise RuntimeError("Another benchmark coordinator is active") from error
        try:
            yield
        finally:
            _unlock(handle)
