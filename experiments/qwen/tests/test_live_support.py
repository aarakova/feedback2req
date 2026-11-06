"""Offline tests of explicit prompts, comparison controls and permission gates."""

import argparse
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from test_experiment import envelope, fixture

from ai.group_findings.prompt import SYSTEM_PROMPT as PRODUCT
from ai.group_findings.validation import GroupingError
from experiments.qwen.adapter import ExperimentalOllama, config_check
from experiments.qwen.bootstrap_cloud import (
    approvals,
    ensure_port_free,
    owns_listener,
    require_owned_server,
)
from experiments.qwen.dataset import load_cases
from experiments.qwen.f2_provider import F2LocalProvider
from experiments.qwen.portable import matrix, resources, seal_archive
from experiments.qwen.profiles import prompt_profile


class LiveSupportTests(unittest.TestCase):
    def test_sealed_archive_manifest_and_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.zip"
            output = Path(folder) / "bundle.zip"
            with ZipFile(source, "x") as archive:
                archive.comment = b"a" * 40
                archive.writestr("ai/__init__.py", "# synthetic-source")
            with patch("experiments.qwen.portable.local_output", return_value=output):
                sealed = seal_archive(source, "a" * 40, output)
            self.assertEqual(sealed["files"], 1)
            with ZipFile(output) as archive:
                manifest = json.loads(archive.read("BUNDLE-MANIFEST.json"))
                self.assertEqual(manifest["revision"], "a" * 40)
            unsafe = Path(folder) / "unsafe.zip"
            with ZipFile(unsafe, "x") as archive:
                archive.comment = b"a" * 40
                archive.writestr(".env", "not-for-export")
            with (
                patch(
                    "experiments.qwen.portable.local_output",
                    return_value=Path(folder) / "bad.zip",
                ),
                self.assertRaises(ValueError),
            ):
                seal_archive(unsafe, "a" * 40, Path(folder) / "bad.zip")

    def test_seal_rejects_wrong_git_archive_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "wrong.zip"
            with ZipFile(source, "x") as archive:
                archive.comment = b"b" * 40
                archive.writestr("ai/__init__.py", "# synthetic-source")
            with (
                patch(
                    "experiments.qwen.portable.local_output",
                    return_value=Path(folder) / "out.zip",
                ),
                self.assertRaisesRegex(ValueError, "revision_comment_mismatch"),
            ):
                seal_archive(source, "a" * 40, Path(folder) / "out.zip")

    @unittest.skipUnless(
        Path("/proc/net/tcp").is_file(), "Linux-only bootstrap ownership check"
    )
    def test_occupied_port_and_actual_listener_ownership(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 11435))
            listener.listen()
            with self.assertRaisesRegex(ValueError, "occupied"):
                ensure_port_free()
            self.assertTrue(owns_listener(os.getpid()))
            require_owned_server(SimpleNamespace(pid=os.getpid(), poll=lambda: None))
            with self.assertRaises(ValueError):
                require_owned_server(SimpleNamespace(pid=os.getpid(), poll=lambda: 1))

    def test_notebook_is_unexecuted_and_code_cells_compile(self):
        notebook = json.loads(
            (Path(__file__).parents[1] / "Qwen35-Free-GPU.ipynb").read_text("utf-8")
        )
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])
                compile("".join(cell["source"]), f"notebook-cell-{index}", "exec")

    @unittest.skipUnless(
        Path("/proc/meminfo").is_file(), "Linux cgroup memory measurement"
    )
    def test_cgroup_limit_caps_host_memory(self):
        values = {
            "/proc/meminfo": "MemAvailable: 33554432 kB\n",
            "/sys/fs/cgroup/memory.max": str(3 * 1024**3),
            "/sys/fs/cgroup/memory.current": str(1024**3),
        }
        with (
            patch.object(
                Path,
                "read_text",
                autospec=True,
                side_effect=lambda path, *a, **k: values[str(path)],
            ),
            patch(
                "experiments.qwen.portable.capture",
                return_value="0, Synthetic GPU, 24576, 20000, 600.0",
            ),
        ):
            state = resources()
        self.assertEqual(state["available_ram_bytes"], 2 * 1024**3)
        self.assertFalse(state["qwen35_9b_gpu_candidate"])

    def test_product_prompt_exact_and_profile_closed(self):
        cfg = matrix()["qwen35-9b-product-matched"]
        self.assertEqual(prompt_profile(cfg)[2], PRODUCT)
        messages = []

        def transport(path, body, *args):
            messages.extend(body["messages"])
            return envelope(model=cfg["model"])

        ExperimentalOllama(cfg, enabled=True, transport=transport).group(fixture()[0])
        self.assertEqual(messages[0]["content"], PRODUCT)
        self.assertEqual(json.loads(messages[1]["content"]), fixture()[0])
        cfg["prompt_profile"] = "unapproved"
        with self.assertRaises(GroupingError):
            config_check(cfg)

    def test_matched_sampling_and_f2_deadline(self):
        configs = matrix()
        self.assertEqual(len(configs), 4)
        all_options = [config_check(cfg)["options"] for cfg in configs.values()]
        self.assertTrue(all(options == all_options[0] for options in all_options))
        self.assertTrue(all(cfg["timeout_seconds"] == 90 for cfg in configs.values()))
        recommended = matrix("recommended")
        self.assertNotEqual(
            recommended["qwen3-4b-product-recommended"]["options"],
            recommended["qwen35-9b-product-recommended"]["options"],
        )

    def test_dksu_are_valid_and_preliminary(self):
        _, cases, _ = load_cases()
        self.assertTrue(
            {
                "D-conflict",
                "K-conditions",
                "S-compatible",
                "U-insufficient",
                "D-independent",
                "U-injection",
            }
            <= {case["id"] for case in cases}
        )
        self.assertTrue(
            all(
                case["annotation"]["status"] == "preliminary"
                for case in cases
                if case["id"].startswith(("D-", "K-", "S-", "U-"))
            )
        )

    def test_cloud_authorization_gates(self):
        args = argparse.Namespace(
            approved_runtime=False,
            approved_weights=True,
            approved_synthetic_transfer=True,
            free_runtime_confirmed=True,
        )
        with self.assertRaises(ValueError):
            approvals(args)
        args.approved_runtime = True
        approvals(args)

    def test_unknown_gpu_is_not_a_gpu_allocation(self):
        with patch("experiments.qwen.portable.capture", return_value=None):
            state = resources()
        self.assertFalse(state["qwen35_9b_gpu_candidate"])
        self.assertEqual(state["gpus"], [])

    def test_f2_budget_gate_before_identity(self):
        config = matrix()["qwen35-9b-product-matched"]
        config["timeout_seconds"] = 121
        with patch("experiments.qwen.f2_provider.bounded_identity") as identity:
            with self.assertRaisesRegex(GroupingError, "f2_deadline_budget"):
                F2LocalProvider(
                    config, {}, "unused", approved=True, synthetic_data=True
                )
            identity.assert_not_called()

    def test_f2_precall_failure_keeps_ai_not_performed(self):
        config = matrix()["qwen35-9b-product-matched"]
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("experiments.qwen.f2_provider.bounded_identity", return_value={}),
            patch(
                "experiments.qwen.f2_provider.output_path",
                return_value=Path(folder) / "attempt",
            ),
            patch(
                "experiments.qwen.f2_provider.bounded_execute",
                return_value={
                    "raw": None,
                    "content": None,
                    "candidate": None,
                    "request_attempted": False,
                    "error": {"code": "invalid_request", "rule": "context_budget"},
                },
            ),
        ):
            provider = F2LocalProvider(
                config, {}, "unused", approved=True, synthetic_data=True
            )
            with self.assertRaisesRegex(GroupingError, "provider_not_configured"):
                provider.group(fixture()[0])
            evidence = json.loads((provider.output / "diagnostics.json").read_text())
            self.assertEqual(evidence["error"]["rule"], "context_budget")

    def test_f2_canonical_failure_returns_unrepaired_content_to_component(self):
        config = matrix()["qwen35-9b-product-matched"]
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("experiments.qwen.f2_provider.bounded_identity", return_value={}),
            patch(
                "experiments.qwen.f2_provider.output_path",
                return_value=Path(folder) / "attempt",
            ),
            patch(
                "experiments.qwen.f2_provider.bounded_execute",
                return_value={
                    "raw": b"{}",
                    "content": "{}",
                    "candidate": None,
                    "request_attempted": True,
                    "provider_completed": True,
                    "error": {"code": "invalid_response", "rule": "schema"},
                },
            ),
        ):
            provider = F2LocalProvider(
                config, {}, "unused", approved=True, synthetic_data=True
            )
            self.assertEqual(provider.group(fixture()[0]), "{}")


if __name__ == "__main__":
    unittest.main()
