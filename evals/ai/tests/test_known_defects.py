#!/usr/bin/env python3
"""Mandatory regressions for defects reproduced from QA commit 7f9fca4.

These assert approved structural/provenance/coverage rules, not semantic gold.
The four original assertions are preserved; discovery and CI must run them.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from checks import check_request, check_response
from runner import Dataset


class KnownDefectRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = Dataset()

    def previous_context(self):
        example = copy.deepcopy(self.dataset.examples[("S01", "extract")])
        prepared = self.dataset.examples[("S01", "generate")]["request"]["input"]
        segment = example["request"]["input"]["segments"][0]
        fragment = copy.deepcopy(prepared["fragments"][0])
        fragment.update(
            key="previous-fragment",
            source_ref=segment["source_ref"],
            text_ref=segment["text_ref"],
            quote=segment["text"],
            locator=segment["locator"],
            reliability=segment["reliability"],
        )
        finding = copy.deepcopy(prepared["findings"][0])
        finding["key"] = "previous-finding"
        finding["evidence"][0]["fragment_key"] = fragment["key"]
        example["request"]["input"].update(
            previous_fragments=[fragment], previous_findings=[finding]
        )
        example["trusted"]["states"].extend([fragment["ref"], finding["ref"]])
        self.assertEqual(
            check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            ),
            [],
        )
        return example

    def test_previous_fragment_quote_must_match_its_trusted_text(self):
        example = self.previous_context()
        example["request"]["input"]["previous_fragments"][0]["quote"] = "WRONG-QUOTE"
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("LOCATOR-OR-TEXT", {e["code"] for e in errors})

    def test_previous_fragment_locator_must_be_within_its_trusted_text(self):
        example = self.previous_context()
        example["request"]["input"]["previous_fragments"][0]["locator"] = {
            "start": 9999,
            "end": 10000,
        }
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("LOCATOR-OR-TEXT", {e["code"] for e in errors})

    def test_previous_fragment_reliability_must_match_its_trusted_text(self):
        example = self.previous_context()
        example["request"]["input"]["previous_fragments"][0]["reliability"] = (
            "uncertain"
        )
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("RELIABILITY-MISMATCH", {e["code"] for e in errors})

    def test_not_processed_verification_cannot_publish_substantive_issues(self):
        example = copy.deepcopy(self.dataset.examples[("S06", "verify")])
        response = example["fixture_response"]
        self.assertTrue(response["result"]["issues"])
        response["coverage"][0].update(
            reviewed=False, disposition="not_processed", reason="Not reviewed"
        )
        for assessment in response["result"]["checks"]:
            assessment["considered_keys"] = []
        errors, _ = check_response(
            self.dataset.contracts, example["request"], response, example["trusted"]
        )
        self.assertTrue(
            errors, "Substantive issues from an unreviewed target must be rejected"
        )

    def test_previous_fragment_source_and_missing_text_are_checked(self):
        for field, code in (
            ("source_ref", "SOURCE-MISMATCH"),
            ("text_ref", "TEXT-STATE-UNAVAILABLE"),
        ):
            with self.subTest(field=field):
                example = self.previous_context()
                fragment = example["request"]["input"]["previous_fragments"][0]
                fragment[field] = {**fragment[field], "state_id": "other-state"}
                example["trusted"]["states"].append(fragment[field])
                errors = check_request(
                    self.dataset.contracts, example["request"], example["trusted"]
                )
                self.assertIn(code, {e["code"] for e in errors})

    def test_previous_speech_preserves_mapping_and_cannot_promote_reliability(self):
        example = self.previous_context()
        fragment = example["request"]["input"]["previous_fragments"][0]
        fragment.update(
            text_ref={"kind": "transcript", "id": "speech", "state_id": "v1"},
            reliability="uncertain",
            time_range={"start_ms": 500, "end_ms": 1500},
        )
        example["trusted"]["states"].append(fragment["text_ref"])
        example["trusted"]["texts"].append(
            {
                "ref": copy.deepcopy(fragment["text_ref"]),
                "source_ref": copy.deepcopy(fragment["source_ref"]),
                "text": fragment["quote"],
                "reliability": "uncertain",
                "time_range": copy.deepcopy(fragment["time_range"]),
            }
        )
        self.assertEqual(
            check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            ),
            [],
        )
        for mutation, code in (
            ({"reliability": "usable"}, "RELIABILITY-MISMATCH"),
            (
                {"time_range": {"start_ms": 600, "end_ms": 1500}},
                "TIME-MAPPING-MISMATCH",
            ),
            ({"time_range": {"start_ms": 1500, "end_ms": 500}}, "TIME-ORDER"),
        ):
            with self.subTest(code=code):
                changed = copy.deepcopy(example)
                changed["request"]["input"]["previous_fragments"][0].update(mutation)
                errors = check_request(
                    self.dataset.contracts, changed["request"], changed["trusted"]
                )
                self.assertIn(code, {e["code"] for e in errors})

    def test_valid_previous_unicode_substring_uses_absolute_codepoint_offsets(self):
        example = self.previous_context()
        prefix, content = "\U0001f9ed", "\U0001f600e\u0301\r\nx"
        example["trusted"]["texts"][0]["text"] = prefix + content
        segment = example["request"]["input"]["segments"][0]
        fragment = example["request"]["input"]["previous_fragments"][0]
        segment.update(text=content, locator={"start": 1, "end": 1 + len(content)})
        fragment.update(quote=content, locator=copy.deepcopy(segment["locator"]))
        self.assertEqual(
            check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            ),
            [],
        )
        fragment["locator"] = {"start": 2, "end": 2 + len(content)}
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("LOCATOR-OR-TEXT", {e["code"] for e in errors})

    def unreviewed_verification(self):
        example = copy.deepcopy(self.dataset.examples[("S06", "verify")])
        response = example["fixture_response"]
        response["coverage"][0].update(
            reviewed=False, disposition="not_processed", reason="Not reviewed"
        )
        for assessment in response["result"]["checks"]:
            assessment.update(considered_keys=[], conclusion="inconclusive")
        return example

    def test_unreviewed_issues_rejected_even_when_all_checks_are_inconclusive(self):
        example = self.unreviewed_verification()
        self.assertTrue(example["fixture_response"]["result"]["issues"])
        errors, _ = check_response(
            self.dataset.contracts,
            example["request"],
            example["fixture_response"],
            example["trusted"],
        )
        self.assertIn("RESULT-FROM-UNREVIEWED", {e["code"] for e in errors})

    def test_unreviewed_target_can_report_only_inconclusive_empty_checks(self):
        example = self.unreviewed_verification()
        response = example["fixture_response"]
        response["result"]["issues"] = []
        errors, _ = check_response(
            self.dataset.contracts, example["request"], response, example["trusted"]
        )
        self.assertEqual(errors, [])
        for conclusion in ("no_issue_found", "issues_found"):
            with self.subTest(conclusion=conclusion):
                response["result"]["checks"][0]["conclusion"] = conclusion
                errors, _ = check_response(
                    self.dataset.contracts,
                    example["request"],
                    response,
                    example["trusted"],
                )
                self.assertIn("RESULT-FROM-UNREVIEWED", {e["code"] for e in errors})

    def test_previous_fragment_diagnostics_are_private_and_do_not_repair_input(self):
        example = self.previous_context()
        marker = "PRIVATE-PREVIOUS-FRAGMENT-SENTINEL"
        example["request"]["input"]["previous_fragments"][0]["quote"] = marker
        before = copy.deepcopy(example)
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("LOCATOR-OR-TEXT", {e["code"] for e in errors})
        self.assertEqual(example, before)
        self.assertNotIn(marker, json.dumps(errors))


if __name__ == "__main__":
    unittest.main()
