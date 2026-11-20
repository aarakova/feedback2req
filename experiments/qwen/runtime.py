"""Bounded cleanup for the Linux bootstrap's own process group only.

No daemon discovery or killing by executable name. Ollama must be launched with
start_new_session=True by this bootstrap. Detached processes are not controlled;
actual model-runner lifecycle still needs measurement on an approved runtime.
"""

import os
import signal
import subprocess
import time
from pathlib import Path


def group_members(group_id):
    """Linux live members; zombies cannot compute and are excluded explicitly."""
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            # comm may contain spaces or parentheses. Fields after its last ')'
            # begin with state, ppid, pgrp; do not split the entire stat record.
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == group_id and fields[0] not in {"Z", "X"}:
                members.append(int(entry.name))
        except FileNotFoundError:
            continue
    return sorted(members)


def stop_owned_group(server, *, grace_seconds=5):
    """Signal only our new-session group, including children after parent exit.

    Returned evidence is a process-group observation, not a GPU-memory sample.
    The caller records failure rather than claiming successful cancellation.
    """
    group_id = server.pid
    if os.name != "posix" or group_id <= 1 or group_id == os.getpgrp():
        raise ValueError("Invalid owned process group")
    if server.poll() is None:
        try:
            if os.getpgid(server.pid) != group_id:
                raise ValueError("Server was not started in its own process group")
        except ProcessLookupError:
            pass  # Parent exited; its still-live group must also be stopped.
    evidence = {"process_group_id": group_id, "signals": [], "live_members": None}
    for sig, timeout in ((signal.SIGTERM, grace_seconds), (signal.SIGKILL, 2)):
        try:
            os.killpg(group_id, sig)
            evidence["signals"].append(sig.name)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + timeout
        while True:
            server.poll()  # Reap the direct child independently of its runners.
            try:
                evidence["live_members"] = group_members(group_id)
            except (OSError, ValueError, IndexError):
                # Inspection failure must not bypass SIGKILL or be reported as
                # proof of shutdown. Preserve only a safe technical marker.
                evidence["live_members"] = None
                evidence["inspection_error"] = "process_group_measurement_failed"
                break
            if not evidence["live_members"] or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        if evidence["live_members"] == []:
            evidence["status"] = "no_live_process_group_members"
            return evidence
    evidence["status"] = "cleanup_failed"
    return evidence


def start_owned_server(binary, environment, log, cwd):
    """Linux bootstrap only; do not inherit the notebook/client process group."""
    if os.name != "posix" or not Path("/proc/net/tcp").is_file():
        raise ValueError("Owned bootstrap requires Linux process inspection")
    return subprocess.Popen(
        [str(binary), "serve"],
        env=environment,
        stdout=log,
        stderr=log,
        cwd=cwd,
        start_new_session=True,
    )
