"""Sample the dedicated Linux process group and selected GPU, never model text.

RSS sums may double-count shared pages. CPU deltas and sampled peaks can miss
short-lived runners. GPU memory is device-wide, not attributed model VRAM.
"""

import json
import os
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

from .runtime import group_members


def process_sample(group_id):
    values = []
    for pid in group_members(group_id):
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        except FileNotFoundError:
            continue
        if int(fields[2]) == group_id and fields[0] not in {"Z", "X"}:
            values.append(
                {
                    "pid": pid,
                    "start_ticks": int(fields[19]),
                    "cpu_ticks": int(fields[11]) + int(fields[12]),
                    "rss_bytes": max(0, int(fields[21])) * os.sysconf("SC_PAGE_SIZE"),
                }
            )
    return values


def gpu_sample(index):
    if index is None:
        return None
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                f"--id={index}",
                "--query-gpu=memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        used, free, utilization = [
            int(value.strip()) for value in result.stdout.split(",")
        ]
        if used < 0 or free < 0 or not 0 <= utilization <= 100:
            return None
        return {
            "index": index,
            "used_bytes": used * 1048576,
            "free_bytes": free * 1048576,
            "utilization_percent": utilization,
            "scope": "device_wide_not_model_attributed",
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


class ResourceMonitor:
    """Read-only measurements; stop_owned_group remains the independent control."""

    def __init__(self, group_id, output, *, gpu_index=None, interval_seconds=1):
        if type(group_id) is not int or group_id <= 1:
            raise ValueError("invalid_process_group")
        if gpu_index is not None and (type(gpu_index) is not int or gpu_index < 0):
            raise ValueError("invalid_gpu_index")
        if not 0.1 <= interval_seconds <= 5:
            raise ValueError("invalid_sampling_interval")
        self.group_id, self.output = group_id, Path(output)
        self.gpu_index, self.interval = gpu_index, interval_seconds
        self.stop = threading.Event()
        self.stream, self.thread = None, None
        self.previous = {}
        self.cpu_seconds = 0
        self.rss_peak, self.gpu_peak = None, None
        self.gpu_before, self.gpu_after = None, None
        self.samples, self.process_samples, self.process_errors, self.gpu_errors = (
            0,
            0,
            0,
            0,
        )
        self.write_error = None

    def sample(self):
        row = {
            "measured_at": datetime.now(UTC).isoformat(),
            "process_group_id": self.group_id,
            "processes": None,
            "rss_sum_bytes": None,
            "process_measurement_error": None,
        }
        try:
            processes = process_sample(self.group_id)
            current = {(p["pid"], p["start_ticks"]): p["cpu_ticks"] for p in processes}
            delta = sum(
                max(0, ticks - self.previous.get(key, ticks))
                for key, ticks in current.items()
            )
            self.cpu_seconds += delta / os.sysconf("SC_CLK_TCK")
            self.previous = current
            row["processes"] = processes
            row["rss_sum_bytes"] = sum(p["rss_bytes"] for p in processes)
            self.rss_peak = max(self.rss_peak or 0, row["rss_sum_bytes"])
            self.process_samples += 1
        except (OSError, ValueError, IndexError):
            self.process_errors += 1
            row["process_measurement_error"] = "process_sample_unavailable"
        gpu = gpu_sample(self.gpu_index)
        if self.samples == 0:
            self.gpu_before = gpu
        if gpu:
            self.gpu_peak = max(self.gpu_peak or 0, gpu["used_bytes"])
        elif self.gpu_index is not None:
            self.gpu_errors += 1
        self.gpu_after = gpu
        row.update(
            gpu=gpu,
            cpu_seconds_observed_delta_sum=self.cpu_seconds
            if self.process_samples
            else None,
        )
        self.stream.write(json.dumps(row, allow_nan=False) + "\n")
        self.stream.flush()
        self.samples += 1

    def loop(self):
        while not self.stop.wait(self.interval):
            try:
                self.sample()
            except OSError:
                self.write_error = "resource_log_write_failed"
                return

    def start(self):
        self.stream = self.output.open("x", encoding="utf-8")
        try:
            self.sample()  # Baseline before the first model request.
        except OSError:
            self.stream.close()
            raise
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
        stopped = not self.thread.is_alive()
        if stopped:
            try:
                self.sample()  # Bootstrap calls close after runtime shutdown.
            except OSError:
                self.write_error = "resource_log_write_failed"
            finally:
                self.stream.close()
        return {
            "mode": "sampled_process_group_and_device",
            "measurement_version": "linux-process-group-device-v1",
            "process_group_id": self.group_id,
            "interval_seconds": self.interval,
            "samples": self.samples,
            "valid_process_samples": self.process_samples,
            "sampler_stopped": stopped,
            "write_error": self.write_error,
            "process_sample_errors": self.process_errors,
            "gpu_sample_errors": self.gpu_errors,
            "rss_sum_peak_observed_bytes": self.rss_peak,
            "cpu_seconds_observed_delta_sum": self.cpu_seconds
            if self.process_samples
            else None,
            "device_used_peak_observed_bytes": self.gpu_peak,
            "gpu_before": self.gpu_before,
            "gpu_after_shutdown_attempt": self.gpu_after if stopped else None,
            "model_peak_vram_bytes": None,
            "limitations": "Sampled, not exact peaks; RSS can double-count shared pages. CPU deltas miss first samples/short-lived processes and use PID+starttime identities. GPU is device-wide, not model attributed; release is not inferred from these values. Detached groups are not measured.",
        }
