#!/usr/bin/env python3
"""Opt-in failing QA regressions. Run separately; NOT part of tests/ discovery.

These assert approved structural/provenance/coverage rules, not semantic gold.
No xfail/skip and no production fixes: failure is the evidence until corrected.
"""

from __future__ import annotations

import copy
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


if __name__ == "__main__":
    unittest.main()
