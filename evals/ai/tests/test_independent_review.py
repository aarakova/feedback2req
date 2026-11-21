#!/usr/bin/env python3
"""Independent boundary tests; no application, database, provider, or golden semantics."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from checks import InputError, check_request, check_response, strict_load
from runner import Dataset, compare_reports, evaluate, write_comparison


class IndependentReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = Dataset()
        cls.controls = strict_load(cls.dataset.root / "replays/controls.json")

    def example(self):
        return copy.deepcopy(self.dataset.examples[("S01", "extract")])

    def evaluate_replay(self, replay, root):
        path = root / "replay.json"
        path.write_text(json.dumps(replay), encoding="utf-8")
        return evaluate(self.dataset, path)

    def test_nested_unknown_field_is_rejected_without_echo_or_mutation(self):
        example = self.example()
        marker = "PRIVATE-NESTED-FIELD-SENTINEL"
        example["fixture_response"]["result"]["findings"][0][marker] = marker
        original = copy.deepcopy(example)
        errors, facts = check_response(
            self.dataset.contracts,
            example["request"],
            example["fixture_response"],
            example["trusted"],
        )
        self.assertTrue(errors)
        self.assertIn("SCHEMA-ADDITIONALPROPERTIES", {e["code"] for e in errors})
        self.assertNotIn(marker, json.dumps(errors))
        self.assertEqual(facts, {})
        self.assertEqual(example, original)

    def test_input_keys_are_unique_across_document_and_primary_namespaces(self):
        example = self.example()
        example["request"]["input"]["documents"][0]["key"] = example["request"][
            "input"
        ]["segments"][0]["key"]
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("KEYS-NOT-UNIQUE", {e["code"] for e in errors})

    def test_output_ids_are_unique_across_fragments_and_findings(self):
        example = self.example()
        result = example["fixture_response"]["result"]
        result["findings"][0]["local_id"] = result["fragments"][0]["local_id"]
        errors, _ = check_response(
            self.dataset.contracts,
            example["request"],
            example["fixture_response"],
            example["trusted"],
        )
        self.assertIn("LOCAL-IDS-NOT-UNIQUE", {e["code"] for e in errors})

    def test_non_bmp_locator_uses_codepoints_and_rejects_utf16_offsets(self):
        example = self.example()
        prefix, text = "\U0001f9ed", "\U0001f9edx\r\ne\u0301"
        source = example["trusted"]["texts"][0]
        source["text"] = prefix + text
        segment = example["request"]["input"]["segments"][0]
        segment.update(
            text=text, locator={"start": len(prefix), "end": len(prefix + text)}
        )
        fragment = example["fixture_response"]["result"]["fragments"][0]
        fragment.update(quote="e\u0301", occurrence=0)
        self.assertEqual(
            check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            ),
            [],
        )
        errors, facts = check_response(
            self.dataset.contracts,
            example["request"],
            example["fixture_response"],
            example["trusted"],
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            facts["derived_fragments"][0]["locator"], {"start": 5, "end": 7}
        )
        segment["locator"]["start"] = len(prefix.encode("utf-16-le")) // 2
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("LOCATOR-OR-TEXT", {e["code"] for e in errors})

    def test_response_symlink_cannot_escape_the_replay_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inside = root / "input"
            inside.mkdir()
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            (inside / "response.json").symlink_to(outside)
            replay = copy.deepcopy(self.controls)
            replay["records"] = replay["records"][:1]
            record = replay["records"][0]
            del record["response"]
            record["response_file"] = "response.json"
            with self.assertRaisesRegex(InputError, "PATH-OUTSIDE"):
                self.evaluate_replay(replay, inside)

    def test_boolean_attempt_and_duration_are_rejected_as_metadata_errors(self):
        for field in ("attempt", "duration_ms"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                replay = copy.deepcopy(self.controls)
                replay["records"] = replay["records"][:1]
                replay["records"][0][field] = True
                with self.assertRaises(InputError):
                    self.evaluate_replay(replay, Path(directory))

    def test_changed_external_response_bytes_invalidate_an_expert_form(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = copy.deepcopy(self.controls)
            replay["records"] = replay["records"][:1]
            record = replay["records"][0]
            response = root / "response.json"
            response.write_text(json.dumps(record.pop("response")), encoding="utf-8")
            record["response_file"] = "response.json"
            _, template = self.evaluate_replay(replay, root)
            template["reviewer"] = "Independent synthetic reviewer"
            expert = root / "expert.json"
            expert.write_text(json.dumps(template), encoding="utf-8")
            response.write_text(
                response.read_text(encoding="utf-8") + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(InputError, "EXPERT-BINDING-MISMATCH"):
                evaluate(self.dataset, root / "replay.json", expert)

    def test_schema_drift_and_existing_comparison_output_are_rejected(self):
        report, _ = evaluate(self.dataset, self.dataset.root / "replays/controls.json")
        changed = copy.deepcopy(report)
        changed["execution"]["schemas_sha256"] = "different-schema-snapshot"
        with self.assertRaisesRegex(InputError, "COMPARE-INCOMPATIBLE"):
            compare_reports(report, changed)
        comparison = compare_reports(report, report)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "comparison"
            write_comparison(comparison, output)
            original = (output / "comparison.json").read_bytes()
            with self.assertRaisesRegex(InputError, "REPORT-DIRECTORY"):
                write_comparison(comparison, output)
            self.assertEqual((output / "comparison.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
