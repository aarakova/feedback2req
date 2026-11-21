"""Measurements of fake data/own tiny processes, no Ollama, GPU or model run."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from test_experiment import envelope

from experiments.qwen.adapter import ExperimentalOllama
from experiments.qwen.bootstrap_cloud import (
    SMOKE_CASES,
    evaluation_command,
    select_gpu_index,
)
from experiments.qwen.dataset import load_cases
from experiments.qwen.portable import matrix
from experiments.qwen.resource_monitor import ResourceMonitor, gpu_sample
from experiments.qwen.runtime import stop_owned_group


class ResourceMonitorTests(unittest.TestCase):
    def test_gpu_selection_respects_existing_allocation(self):
        status = {
            "gpus": [
                {"index": 0, "free_bytes": 20 * 1024**3},
                {"index": 1, "free_bytes": 12 * 1024**3},
            ]
        }
        self.assertEqual(select_gpu_index(status, "1"), 1)
        self.assertEqual(select_gpu_index(status, None), 0)
        status["gpus"][1]["free_bytes"] = 2 * 1024**3
        with self.assertRaisesRegex(
            ValueError, "allocated_visibility|allocated visibility"
        ):
            select_gpu_index(status, "1")

    def test_unknown_or_disabled_gpu_masks_are_not_overridden(self):
        status = {"gpus": [{"index": 0, "free_bytes": 20 * 1024**3}]}
        for visibility in ("", "-1", "GPU-synthetic-uuid", "MIG-synthetic", "all"):
            with self.subTest(visibility=visibility), self.assertRaises(ValueError):
                select_gpu_index(status, visibility)

    def test_suite_commands_keep_explicit_gates_and_existing_inputs(self):
        shared = [
            "--config",
            "synthetic-config.json",
            "--allow-local-inference",
            "--synthetic-only",
        ]
        _, cases, _ = load_cases()
        command, timeout = evaluation_command(shared, "lock", "output", "smoke")
        selected = [
            command[i + 1] for i, value in enumerate(command) if value == "--case"
        ]
        self.assertEqual(tuple(selected), SMOKE_CASES)
        self.assertTrue(set(selected) <= {case["id"] for case in cases})
        self.assertEqual(timeout, 600)
        all_command, all_timeout = evaluation_command(shared, "lock", "output", "all")
        self.assertNotIn("--case", all_command)
        self.assertIn("--allow-local-inference", all_command)
        self.assertIn("--synthetic-only", all_command)
        self.assertEqual(all_timeout, 1020)
        with self.assertRaises(ValueError):
            evaluation_command(shared, "lock", "output", "unknown")

    def test_gpu_is_device_scoped_and_command_is_bounded(self):
        with patch(
            "experiments.qwen.resource_monitor.subprocess.run",
            return_value=MagicMock(stdout="100, 14000, 25\n"),
        ) as command:
            value = gpu_sample(2)
        self.assertEqual(value["used_bytes"], 100 * 1048576)
        self.assertEqual(value["scope"], "device_wide_not_model_attributed")
        self.assertIn("--id=2", command.call_args.args[0])
        self.assertEqual(command.call_args.kwargs["timeout"], 2)

    def test_gpu_missing_or_invalid_is_unknown_not_zero(self):
        for output in ("N/A, N/A, N/A", "-1, 500, 20", "1, 500, 120", "1, 2"):
            with patch(
                "experiments.qwen.resource_monitor.subprocess.run",
                return_value=MagicMock(stdout=output),
            ):
                self.assertIsNone(gpu_sample(0))
        with patch(
            "experiments.qwen.resource_monitor.subprocess.run",
            side_effect=subprocess.TimeoutExpired("nvidia-smi", 2),
        ):
            self.assertIsNone(gpu_sample(0))
        with patch("experiments.qwen.resource_monitor.subprocess.run") as command:
            self.assertIsNone(gpu_sample(None))
        command.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Linux process clock")
    def test_cpu_pid_reuse_and_sampled_peaks(self):
        process_rows = [
            [{"pid": 10, "start_ticks": 1, "cpu_ticks": 100, "rss_bytes": 100}],
            [
                {"pid": 10, "start_ticks": 1, "cpu_ticks": 150, "rss_bytes": 100},
                {"pid": 11, "start_ticks": 2, "cpu_ticks": 900, "rss_bytes": 200},
            ],
            [{"pid": 10, "start_ticks": 3, "cpu_ticks": 1000, "rss_bytes": 50}],
        ]
        gpu_rows = [
            {"used_bytes": 100, "scope": "device_wide_not_model_attributed"},
            {"used_bytes": 200, "scope": "device_wide_not_model_attributed"},
            {"used_bytes": 150, "scope": "device_wide_not_model_attributed"},
        ]
        with (
            tempfile.TemporaryDirectory() as folder,
            patch(
                "experiments.qwen.resource_monitor.process_sample",
                side_effect=process_rows,
            ),
            patch("experiments.qwen.resource_monitor.gpu_sample", side_effect=gpu_rows),
            patch("experiments.qwen.resource_monitor.os.sysconf", return_value=100),
        ):
            path = Path(folder) / "samples.jsonl"
            monitor = ResourceMonitor(
                123, path, gpu_index=0, interval_seconds=5
            ).start()
            monitor.sample()
            summary = monitor.close()
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(summary["cpu_seconds_observed_delta_sum"], 0.5)
        self.assertEqual(summary["rss_sum_peak_observed_bytes"], 300)
        self.assertEqual(summary["device_used_peak_observed_bytes"], 200)
        self.assertIsNone(summary["model_peak_vram_bytes"])
        self.assertEqual(summary["gpu_before"]["used_bytes"], 100)
        self.assertEqual(summary["gpu_after_shutdown_attempt"]["used_bytes"], 150)
        self.assertTrue(summary["sampler_stopped"])

    def test_missing_measurements_stay_null_and_file_cannot_be_overwritten(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch(
                "experiments.qwen.resource_monitor.process_sample",
                side_effect=PermissionError,
            ),
            patch("experiments.qwen.resource_monitor.gpu_sample", return_value=None),
        ):
            path = Path(folder) / "samples.jsonl"
            monitor = ResourceMonitor(
                123, path, gpu_index=0, interval_seconds=5
            ).start()
            summary = monitor.close()
            self.assertIsNone(summary["rss_sum_peak_observed_bytes"])
            self.assertIsNone(summary["cpu_seconds_observed_delta_sum"])
            self.assertIsNone(summary["device_used_peak_observed_bytes"])
            self.assertEqual(summary["process_sample_errors"], 2)
            self.assertEqual(summary["gpu_sample_errors"], 2)
            with self.assertRaises(FileExistsError):
                ResourceMonitor(123, path).start()

    def test_unstopped_sampler_cannot_claim_after_shutdown_snapshot(self):
        monitor = ResourceMonitor(123, "not-opened.jsonl")
        monitor.thread = MagicMock()
        monitor.thread.is_alive.return_value = True
        monitor.gpu_after = {"used_bytes": 200}
        summary = monitor.close()
        self.assertFalse(summary["sampler_stopped"])
        self.assertIsNone(summary["gpu_after_shutdown_attempt"])

    def test_missing_baseline_is_not_replaced_by_later_gpu_usage(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("experiments.qwen.resource_monitor.process_sample", return_value=[]),
            patch(
                "experiments.qwen.resource_monitor.gpu_sample",
                side_effect=[None, {"used_bytes": 200}],
            ),
        ):
            monitor = ResourceMonitor(
                123, Path(folder) / "samples.jsonl", interval_seconds=5
            ).start()
            summary = monitor.close()
        self.assertIsNone(summary["gpu_before"])
        self.assertEqual(summary["gpu_after_shutdown_attempt"]["used_bytes"], 200)

    @unittest.skipUnless(Path("/proc/net/tcp").is_file(), "Linux actual process sample")
    def test_own_tiny_process_is_measured_and_shutdown_is_observed(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "ready"
            code = f"import pathlib,time; pathlib.Path({str(marker)!r}).write_text('ready'); time.sleep(20)"
            server = subprocess.Popen(
                [sys.executable, "-c", code], start_new_session=True
            )
            monitor = None
            try:
                deadline = time.monotonic() + 5
                while not marker.is_file() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(marker.is_file())
                monitor = ResourceMonitor(
                    server.pid, Path(folder) / "samples.jsonl"
                ).start()
                cleanup = stop_owned_group(server, grace_seconds=0.1)
                summary = monitor.close()
                monitor = None
                self.assertEqual(cleanup["status"], "no_live_process_group_members")
                self.assertGreater(summary["rss_sum_peak_observed_bytes"], 0)
                self.assertIsNone(summary["device_used_peak_observed_bytes"])
                rows = [
                    json.loads(line)
                    for line in (Path(folder) / "samples.jsonl")
                    .read_text()
                    .splitlines()
                ]
                self.assertEqual(rows[-1]["processes"], [])
            finally:
                stop_owned_group(server, grace_seconds=0.1)
                if monitor is not None:
                    monitor.close()

    def test_recommended_9b_profile_fits_all_existing_synthetic_inputs(self):
        _, cases, _ = load_cases()
        for name, configuration in matrix("recommended").items():
            if "9b" not in name:
                continue
            for case in cases:
                with self.subTest(profile=name, case=case["id"]):
                    transport = MagicMock(
                        return_value=envelope(model=configuration["model"])
                    )
                    adapter = ExperimentalOllama(
                        configuration, enabled=True, transport=transport
                    )
                    adapter.group(case["request"])
                    transport.assert_called_once()
        # No assertion of schema/meaning here: these are request-budget checks,
        # and the synthetic response is deliberately unrelated to most inputs.


if __name__ == "__main__":
    unittest.main()
