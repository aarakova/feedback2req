"""One bounded child at a time; no DB calls in the supervisor process."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from feedback2req.config import Settings
from feedback2req.processing.service import execute_one, worker_database
from feedback2req.runtime import check_schema

STATE = Path("/tmp/f2r-worker-state.json")
LOCK = Path("/tmp/f2r-worker-state.lock")
PASS_SECONDS = 135


def execute_pass(sessions, settings):
    # Keep F1 claim/current_input isolated from finding_set. One compute per pass.
    if execute_one(sessions, settings):
        return True
    from feedback2req.grouping.provider import grouping_provider
    from feedback2req.grouping.queue import execute_queued_grouping

    return execute_queued_grouping(sessions, grouping_provider(settings))


@contextmanager
def state_lock(wait=False):
    with LOCK.open("a") as lock:
        deadline = time.monotonic() + (1 if wait else 0)
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def identity(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def publish(deadline, ready):
    with state_lock(wait=True):
        value = {
            "pid": os.getpid(),
            "start": identity(os.getpid()),
            "deadline": deadline,
            "ready": ready,
        }
        temporary = STATE.with_suffix(".new")
        temporary.write_text(json.dumps(value))
        temporary.replace(STATE)


def probe():
    try:
        with state_lock():
            value = json.loads(STATE.read_text())
            if (
                not isinstance(value, dict)
                or set(value) != {"pid", "start", "deadline", "ready"}
                or type(value["ready"]) is not bool
                or not isinstance(value["start"], str)
                or not value["start"].isdigit()
            ):
                return 1
            pid = value["pid"]
            if (
                type(pid) is not int
                or pid <= 1
                or identity(pid) != value["start"]
                or b"feedback2req.processing.worker"
                not in Path(f"/proc/{pid}/cmdline").read_bytes()
                or b"--once" in Path(f"/proc/{pid}/cmdline").read_bytes()
                or Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1] != "1"
            ):
                return 1
            deadline = value["deadline"]
            if (
                type(deadline) not in {int, float}
                or not 0 < deadline < float("inf")
                or deadline > time.monotonic() + PASS_SECONDS + 1
            ):
                return 1
            descriptor = os.pidfd_open(pid)
            try:
                if identity(pid) != value["start"]:
                    return 1
                if time.monotonic() > deadline:
                    signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                    return 1
            finally:
                os.close(descriptor)
            if value["ready"] is not True:
                return 1
        check_schema(Settings())
        return 0
    except Exception:
        return 1


def supervise():
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # Require the safe signal primitive before accepting any work.
    descriptor = os.pidfd_open(os.getpid())
    os.close(descriptor)
    ready = False
    while not stopping:
        deadline = time.monotonic() + PASS_SECONDS
        publish(deadline, ready)
        child = subprocess.Popen([sys.executable, "-m", "feedback2req.processing.worker", "--once"])
        while child.poll() is None and not stopping and time.monotonic() < deadline:
            time.sleep(0.2)
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)
        if stopping:
            break
        ready = child.returncode == 0
        publish(time.monotonic() + 10, ready)
        for _ in range(5 if ready else 25):
            if stopping:
                break
            time.sleep(0.2)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.probe:
        return probe()
    try:
        if not args.once:
            return supervise()
        settings = Settings()
        check_schema(settings)
        engine, sessions = worker_database(settings.database_url)
        try:
            execute_pass(sessions, settings)
        finally:
            engine.dispose()
        return 0
    except Exception:
        print("Worker pass failed; no unconfirmed operation is replayed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
