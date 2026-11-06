"""No model, installation, network, system change or real-inference result."""

import http.client
import io
import json
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from ai.group_findings.validation import GroupingError, response_format
from experiments.qwen.adapter import ExperimentalOllama, LocalHTTP, config_check
from experiments.qwen.dataset import ROOT, load_cases
from experiments.qwen.run import (
    ResultFile,
    bounded_execute,
    bounded_job,
    execute,
    output_path,
    run,
    write,
)


def cfg():
    return json.loads((Path(__file__).parents[1] / "qwen3-4b.json").read_text())


def fixture():
    root = ROOT / "evals/ai/grouping"
    return (
        json.loads((root / "compatible.request.json").read_text("utf-8")),
        (root / "compatible.response.json").read_text("utf-8"),
    )


def envelope(content=None, **changes):
    result = {
        "model": cfg()["model"],
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": content or fixture()[1]},
        "prompt_eval_count": 500,
        "eval_count": 100,
        "eval_duration": 10000,
    }
    result.update(changes)
    return json.dumps(result, ensure_ascii=False).encode()


def slow_child(configuration, request, sender):
    time.sleep(10)


def empty_child(configuration, request, sender):
    sender.close()


class AdapterTests(unittest.TestCase):
    def test_transfer_gate_before_transport(self):
        transport = MagicMock()
        adapter = ExperimentalOllama(cfg(), transport=transport)
        with self.assertRaisesRegex(GroupingError, "transfer_disabled"):
            adapter.group(fixture()[0])
        transport.assert_not_called()

    def test_config_is_closed_and_bounded(self):
        variants = [
            ("model", "qwen3:4b-cloud"),
            ("ollama_version", "latest"),
            ("think", True),
            ("timeout_seconds", 0),
            ("timeout_seconds", True),
            ("max_response_bytes", 1048577),
            ("endpoint", "https://evil.invalid"),
        ]
        for key, value in variants:
            with self.subTest(key=key):
                value_cfg = cfg()
                value_cfg[key] = value
                with self.assertRaises(GroupingError):
                    config_check(value_cfg)
        for key, value in [
            ("num_ctx", 1000000),
            ("temperature", float("nan")),
            ("num_thread", True),
            ("num_predict", -1),
        ]:
            value_cfg = cfg()
            value_cfg["options"][key] = value
            with self.assertRaises(GroupingError):
                config_check(value_cfg)

    def test_full_messages_schema_options(self):
        request, response = fixture()
        transport = MagicMock(return_value=envelope())
        adapter = ExperimentalOllama(cfg(), enabled=True, transport=transport)
        self.assertEqual(adapter.group(request), response)
        path, body, timeout, limit = transport.call_args.args
        self.assertEqual(path, "/api/chat")
        self.assertEqual(json.loads(body["messages"][1]["content"]), request)
        self.assertEqual(body["format"], response_format())
        self.assertFalse(body["think"])
        self.assertFalse(body["stream"])
        self.assertEqual(body["keep_alive"], 0)
        self.assertEqual(body["options"], cfg()["options"])
        self.assertEqual((timeout, limit), (180, 262144))

    def test_input_and_context_rejected_before_call(self):
        for change, rule in [
            ({"max_request_bytes": 1}, "input_bytes"),
            ({"options": {**cfg()["options"], "num_ctx": 2048}}, "context_budget"),
        ]:
            transport = MagicMock()
            adapter = ExperimentalOllama(
                {**cfg(), **change}, enabled=True, transport=transport
            )
            with self.assertRaisesRegex(GroupingError, rule):
                adapter.group(fixture()[0])
            transport.assert_not_called()

    def test_envelope_and_partial_generation(self):
        variants = [
            ({"done": False}, "provider_envelope"),
            ({"done_reason": "length"}, "generation_incomplete"),
            ({"model": "other"}, "provider_envelope"),
            (
                {
                    "message": {
                        "role": "assistant",
                        "content": "{}",
                        "thinking": "hidden",
                    }
                },
                "provider_envelope",
            ),
            (
                {"message": {"role": "assistant", "content": "{}", "tool_calls": [{}]}},
                "provider_envelope",
            ),
            ({"prompt_eval_count": None}, "prompt_measurement_missing"),
            ({"prompt_eval_count": 8000}, "context_exhausted"),
        ]
        for changes, rule in variants:
            adapter = ExperimentalOllama(
                cfg(),
                enabled=True,
                transport=lambda *a, changes=changes: envelope(**changes),
            )
            with self.assertRaisesRegex(GroupingError, rule):
                adapter.group(fixture()[0])

    def test_transport_errors_are_safe(self):
        for exception, code in [
            (TimeoutError("private"), "timeout"),
            (URLError("private"), "provider_error"),
            (http.client.IncompleteRead(b"private"), "provider_error"),
        ]:
            result = execute(
                cfg(), fixture()[0], transport=MagicMock(side_effect=exception)
            )
            self.assertEqual(result["error"]["code"], code)
            self.assertNotIn("private", str(result))

    def test_bad_json_is_preserved(self):
        for content in [
            '{"coverage":[],"coverage":[]}',
            '{"x":NaN}',
            '{"x":1e999}',
            "{",
        ]:
            raw = envelope(content)
            result = execute(cfg(), fixture()[0], transport=lambda *a, raw=raw: raw)
            self.assertIsNotNone(result["error"])
            self.assertEqual(result["raw"], raw)
            self.assertEqual(result["content"], content)
            self.assertIsNone(result["candidate"])

    def test_size_cap_and_invalid_utf8(self):
        for raw in [b"x" * 262145, b"\xff"]:
            result = execute(cfg(), fixture()[0], transport=lambda *a, raw=raw: raw)
            self.assertIsNotNone(result["error"])
            self.assertEqual(result["raw"], raw)

    def test_schema_and_application_are_separate(self):
        good = execute(cfg(), fixture()[0], transport=lambda *a: envelope())
        self.assertEqual((good["schema"], good["application"]), ("passed", "passed"))
        missing = execute(cfg(), fixture()[0], transport=lambda *a: envelope("{}"))
        self.assertEqual(
            (missing["schema"], missing["application"]), ("failed", "not_run")
        )
        invalid = json.loads(fixture()[1])
        invalid["result"]["groups"][0]["finding_keys"] = ["unknown"]
        bad = execute(
            cfg(), fixture()[0], transport=lambda *a: envelope(json.dumps(invalid))
        )
        self.assertEqual((bad["schema"], bad["application"]), ("passed", "failed"))

    def test_fixed_local_transport_and_no_redirects(self):
        connection = MagicMock()
        connection.getresponse.return_value.status = 302
        with patch(
            "experiments.qwen.adapter.http.client.HTTPConnection",
            return_value=connection,
        ) as constructor:
            with self.assertRaisesRegex(GroupingError, "http_status"):
                LocalHTTP()("/api/chat", {}, 1, 10)
            constructor.assert_called_once_with("127.0.0.1", 11435, timeout=1)
            connection.close.assert_called_once()
        with self.assertRaises(GroupingError):
            LocalHTTP()("https://evil.invalid", {}, 1, 10)

    def test_identity_pins_version_quantization_digest(self):
        values = {
            "/api/version": {"version": "0.40.14"},
            "/api/tags": {
                "models": [{"name": cfg()["model"], "digest": "a" * 64, "size": 100}]
            },
            "/api/show": {
                "details": {"quantization_level": "Q4_K_M"},
                "capabilities": ["completion"],
                "template": "template",
                "model_info": {},
            },
        }
        transport = lambda path, *a: json.dumps(values[path]).encode()
        identity = ExperimentalOllama(
            cfg(), enabled=True, transport=transport
        ).identity()
        self.assertEqual(identity["digest"], "a" * 64)
        for path, key, replacement in [
            ("/api/version", "version", "0.1.0"),
            ("/api/show", "remote_host", "external"),
        ]:
            broken = deepcopy(values)
            broken[path][key] = replacement
            with self.assertRaisesRegex(GroupingError, "runtime_identity"):
                ExperimentalOllama(
                    cfg(),
                    enabled=True,
                    transport=lambda p, *a, broken=broken: json.dumps(
                        broken[p]
                    ).encode(),
                ).identity()

    def test_deadline_terminates_child(self):
        configuration = cfg()
        configuration["timeout_seconds"] = 1
        with patch("experiments.qwen.run.child", slow_child):
            result = bounded_execute(configuration, fixture()[0])
        self.assertEqual(result["error"]["rule"], "wall_deadline")

    def test_crashed_child_is_a_record(self):
        # This checks child failure classification, not a fast startup deadline.
        result = bounded_job(empty_child, (cfg(), fixture()[0]), 30)
        self.assertEqual(result["error"]["rule"], "child_failed")

    def test_incomplete_http_and_error_bodies_are_preserved(self):
        for status, exception in [
            (500, None),
            (200, http.client.IncompleteRead(b"partial")),
        ]:
            connection = MagicMock()
            connection.getresponse.return_value.status = status
            connection.getresponse.return_value.read.return_value = b"server error"
            connection.getresponse.return_value.read.side_effect = exception
            with patch(
                "experiments.qwen.adapter.http.client.HTTPConnection",
                return_value=connection,
            ):
                result = execute(cfg(), fixture()[0])
            self.assertEqual(
                result["raw"], b"partial" if exception else b"server error"
            )
            self.assertIsNotNone(result["error"])

    def test_incomplete_generation_preserves_content(self):
        raw = envelope(done_reason="length")
        result = execute(cfg(), fixture()[0], transport=lambda *a: raw)
        self.assertEqual(result["content"], fixture()[1])
        self.assertFalse(result["provider_completed"])
        self.assertEqual(result["schema"], "not_run")

    def test_invalid_unicode_surrogate_survives_private_result(self):
        data = json.loads(envelope())
        data["message"]["content"] = "\ud800"
        raw = json.dumps(data, ensure_ascii=True).encode()
        result = execute(cfg(), fixture()[0], transport=lambda *a: raw)
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["raw"], raw)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.json"
            ResultFile(path).send(result)
            self.assertEqual(json.loads(path.read_text("utf-8"))["content"], "\ud800")


class DatasetAndRunnerTests(unittest.TestCase):
    def test_mocked_runner_artifacts_and_existing_evaluator(self):
        dataset, cases, _ = load_cases()
        selected = next(c for c in cases if c["id"] == "S05-group")
        response = dataset.examples[tuple(selected["source"])]["fixture_response"]
        result = execute(
            cfg(),
            selected["request"],
            transport=lambda *a: envelope(json.dumps(response)),
        )
        self.assertIsNone(result["error"])
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "mocked-only"
            lock = {"digest": "a" * 64}
            with (
                patch("experiments.qwen.run.bounded_identity", return_value=lock),
                patch("experiments.qwen.run.bounded_execute", return_value=result),
                patch("experiments.qwen.run.output_path", return_value=destination),
                patch("sys.stdout", new_callable=io.StringIO),
            ):
                self.assertEqual(
                    run(
                        cfg(),
                        lock,
                        destination,
                        [selected["id"]],
                        allowed=True,
                        synthetic_only=True,
                    ),
                    0,
                )
            saved = json.loads((destination / "saved-model-responses.json").read_text())
            self.assertEqual(saved["mode"], "saved_model_responses")
            self.assertEqual(saved["records"][0]["outcome"], "returned")
            self.assertTrue(
                (destination / "source-evaluation/expert-review.json").is_file()
            )
            self.assertEqual(
                (destination / "responses/S05-group.envelope.bin").read_bytes(),
                result["raw"],
            )
            # All fake run artifacts are destroyed with this temporary directory.

    def test_lock_mismatch_blocks_inference(self):
        with (
            patch(
                "experiments.qwen.run.bounded_identity",
                return_value={"digest": "actual"},
            ),
            patch("experiments.qwen.run.bounded_execute") as inference,
        ):
            with self.assertRaisesRegex(GroupingError, "lock_mismatch"):
                run(
                    cfg(),
                    {"digest": "different"},
                    "unused",
                    ["G-compatible"],
                    allowed=True,
                    synthetic_only=True,
                )
            inference.assert_not_called()

    def test_dataset_is_reproducible_applicable_and_metamorphic(self):
        _, cases, applicability = load_cases()
        self.assertEqual(set(applicability), {f"S{i:02}" for i in range(1, 15)})
        self.assertTrue(applicability["S05"]["group_findings_examples"])
        self.assertTrue(applicability["S06"]["group_findings_examples"])
        self.assertEqual(cases, load_cases()[1])
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        relations = {c["relationship"]["kind"] for c in cases if c["relationship"]}
        self.assertEqual(relations, {"permutation", "paraphrase"})

    def test_opt_in_before_any_transport(self):
        with patch("experiments.qwen.adapter.LocalHTTP") as transport:
            with self.assertRaises(GroupingError):
                run(cfg(), {}, "unused", [], allowed=False, synthetic_only=True)
            transport.assert_not_called()

    def test_outputs_are_ignored_and_cannot_overwrite(self):
        with self.assertRaises(GroupingError):
            output_path(ROOT / "experiments/qwen/results")
        self.assertEqual(
            output_path(ROOT / ".local/qwen-runs/test"), ROOT / ".local/qwen-runs/test"
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.json"
            write(path, {})
            with self.assertRaises(FileExistsError):
                write(path, {"overwritten": True})


if __name__ == "__main__":
    unittest.main()
