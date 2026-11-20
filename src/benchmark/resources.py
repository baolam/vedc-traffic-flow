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
def simulator_slot(limit=None, timeout=120):
    """Hold one machine-local simulator slot until shutdown: four by default.

    EDGEFLOW_SUMO_SLOTS (up to 16) raises the default for hosts with spare cores; an explicit limit stays 1-4.
    """
    upper = 4
    if limit is None:
        limit, upper = int(os.environ.get("EDGEFLOW_SUMO_SLOTS", 4)), 16
    if type(limit) is not int or not 1 <= limit <= upper:
        raise ValueError(f"SUMO worker limit must be between one and {'four' if upper == 4 else upper}")
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
