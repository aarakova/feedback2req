"""Fault injection ONLY inside the dedicated extraction test worker container."""

import json
import os
import signal
import subprocess
import sys
import time

from feedback2req.processing.worker import STATE, identity, state_lock


def main(mode):
    if os.environ.get("F2R_PROCESSING_TEST_MODE") != "true":
        raise RuntimeError("Probe fault injection requires explicit test mode")
    for _ in range(100):
        with state_lock(wait=True):
            raw = STATE.read_text()
            value = json.loads(raw)
            if value["ready"] and 3 < value["deadline"] - time.monotonic() < 20:
                pid = value["pid"]
                assert pid > 1 and identity(pid) == value["start"]
                os.kill(pid, signal.SIGSTOP)
                break
        time.sleep(0.2)
    else:
        raise RuntimeError("No idle supervisor phase observed")
    if mode == "corrupt":
        try:
            STATE.write_text("{bad-state")
            result = subprocess.run(
                [sys.executable, "-m", "feedback2req.processing.worker", "--probe"],
                timeout=8,
                check=False,
            )
            assert result.returncode == 1
            assert identity(pid) == value["start"]
            with open(f"/proc/{pid}/stat") as stat:
                assert ") T " in stat.read()
            print(
                "PASS: corrupt snapshot returns unhealthy without killing a frozen supervisor"
            )
        finally:
            STATE.write_text(raw)
            os.kill(pid, signal.SIGCONT)
    elif mode == "hang":
        print(
            "Injected SIGSTOP in supervisor idle phase; Docker probe must cause restart",
            flush=True,
        )
    else:
        os.kill(pid, signal.SIGCONT)
        raise ValueError("Unknown test mode")


if __name__ == "__main__":
    main(sys.argv[1])
