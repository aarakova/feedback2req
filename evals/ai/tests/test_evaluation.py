#!/usr/bin/env python3
"""Run with python -B -m unittest discover -s evals/ai/tests -v."""

from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOME))

from checks import InputError, check_request, check_response, strict_load
from cli import main
from runner import (
    DEFAULT_DATASET,
    Dataset,
    compare_reports,
    digest,
    evaluate,
    markdown,
    write_report,
)


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = Dataset()
        cls.controls = DEFAULT_DATASET / "replays/controls.json"
        cls.faults = DEFAULT_DATASET / "replays/faults.json"

    def example(self, case="S01", name="extract"):
        return copy.deepcopy(self.dataset.examples[(case, name)])

    def codes(self, example):
        errors, facts = check_response(
            self.dataset.contracts,
            example["request"],
            example["fixture_response"],
            example["trusted"],
        )
        return {e["code"] for e in errors}, facts

    def test_inventory_annotations_and_traceability(self):
        self.assertEqual(set(self.dataset.cases), {f"S{i:02}" for i in range(1, 15)})
        self.assertEqual(len(self.dataset.examples), 46)
        for case in self.dataset.cases.values():
            with self.subTest(case=case["id"]):
                self.assertEqual(case["annotation"]["status"], "preliminary")
                self.assertTrue(case["traceability"]["contract_rules"])
                self.assertTrue(case["synthetic"])

    def test_all_controls_and_no_automatic_semantic_verdict(self):
        report, template = evaluate(self.dataset, self.controls)
        self.assertEqual(report["summary"]["records"], 46)
        self.assertFalse(report["final_model_quality_assessment"])
        for row in report["records"]:
            with self.subTest(case=row["case_id"], example=row["example_id"]):
                self.assertEqual(row["automatic"]["diagnostics"], [])
                self.assertEqual(row["expert"]["status"], "pending")
                self.assertFalse(row["automatic"]["facts"]["semantic_reading_proven"])
        self.assertEqual(len(template["records"]), 46)

    def test_each_intentional_fault_detected_and_source_unchanged(self):
        before = self.faults.read_bytes()
        report, _ = evaluate(self.dataset, self.faults)
        expectations = strict_load(DEFAULT_DATASET / "replays/fault-expectations.json")
        self.assertEqual(len(expectations), len(report["records"]))
        for row, expected in zip(report["records"], expectations):
            with self.subTest(expected=expected):
                self.assertIn(
                    expected["expected_code"],
                    {e["code"] for e in row["automatic"]["diagnostics"]},
                )
                self.assertEqual(row["expert"]["status"], "pending")
        self.assertEqual(self.faults.read_bytes(), before)
        self.assertEqual(report["summary"]["failed"], 4)

    def test_semantically_wrong_but_structural_response_needs_expert(self):
        example = self.example()
        example["fixture_response"]["result"]["findings"][0]["text"] = (
            "Нужно заменить продукт кофеваркой."
        )
        codes, _ = self.codes(example)
        self.assertEqual(
            codes, set()
        )  # Must never pretend that structural checks prove meaning.

    def test_unicode_exact_second_occurrence(self):
        example = self.example("S11", "unicode-repeated")
        codes, facts = self.codes(example)
        self.assertEqual(codes, set())
        text = example["request"]["input"]["segments"][0]["text"]
        quote = example["fixture_response"]["result"]["fragments"][0]["quote"]
        self.assertEqual(
            facts["derived_fragments"][0]["locator"],
            {"start": text.rfind(quote), "end": text.rfind(quote) + len(quote)},
        )

    def test_overlapping_occurrences_and_nonzero_source_offset(self):
        example = self.example()
        segment = example["request"]["input"]["segments"][0]
        segment.update(text="ааа", locator={"start": 6, "end": 9})
        example["trusted"]["texts"][0]["text"] = "prefixааа"
        example["fixture_response"]["result"]["fragments"][0].update(
            quote="аа", occurrence=1
        )
        self.assertEqual(
            check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            ),
            [],
        )
        codes, facts = self.codes(example)
        self.assertEqual(codes, set())
        self.assertEqual(
            facts["derived_fragments"][0]["locator"], {"start": 7, "end": 9}
        )

    def test_quote_normalization_not_allowed(self):
        example = self.example("S11", "unicode-repeated")
        example["fixture_response"]["result"]["fragments"][0].update(
            quote="хочу сохранять фильтры.", occurrence=0
        )
        self.assertIn("QUOTE-OCCURRENCE", self.codes(example)[0])

    def test_request_coordinate_state_reliability_and_time_corruption(self):
        for field, value, code in (
            ("locator", {"start": 0, "end": 1}, "LOCATOR-OR-TEXT"),
            (
                "text_ref",
                {"kind": "transcript", "id": "missing", "state_id": "v9"},
                "STATE-NOT-IN-FIXTURE",
            ),
            ("reliability", "uncertain", "RELIABILITY-MISMATCH"),
            ("time_range", {"start_ms": 1200, "end_ms": 1300}, "TIME-MAPPING-MISMATCH"),
        ):
            with self.subTest(field=field):
                example = self.example("S10", "speech-usable")
                example["request"]["input"]["segments"][0][field] = value
                errors = check_request(
                    self.dataset.contracts, example["request"], example["trusted"]
                )
                self.assertIn(code, {e["code"] for e in errors})

    def test_project_and_document_snapshot_mismatch(self):
        example = self.example()
        example["request"]["project_id"] = "OTHER-PROJECT"
        example["request"]["input"]["documents"][0]["text"] = "Другой документ."
        codes = {
            e["code"]
            for e in check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            )
        }
        self.assertTrue({"PROJECT-MISMATCH", "DOCUMENT-LOCATOR-OR-TEXT"} <= codes)

    def test_incomplete_history_not_silently_replaced(self):
        example = self.example("S13", "previous-blocker")
        example["request"]["input"]["previous_checks"] = []
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("HISTORY-CONTEXT-MISMATCH", {e["code"] for e in errors})

    def test_comparison_snapshot_not_trusted_from_model(self):
        example = self.example("S13", "other-proposal")
        example["request"]["input"]["comparisons"] = []
        errors = check_request(
            self.dataset.contracts, example["request"], example["trusted"]
        )
        self.assertIn("COMPARISON-SNAPSHOT-MISMATCH", {e["code"] for e in errors})

    def test_overlap_groups_allowed(self):
        example = self.example("S05", "group")
        groups = example["fixture_response"]["result"]["groups"]
        additional = copy.deepcopy(groups[0])
        additional["local_id"] = "group-2"
        groups.append(additional)
        self.assertEqual(self.codes(example)[0], set())

    def test_completed_group_must_account_for_every_finding(self):
        example = self.example("S05", "group")
        example["fixture_response"]["result"]["groups"][0]["finding_keys"] = ["f1"]
        self.assertIn("GROUP-COVERAGE", self.codes(example)[0])

    def test_per_finding_empty_generation_needs_reason(self):
        example = self.example("S05", "generate")
        candidate = example["fixture_response"]["result"]["requirements"][0]
        candidate["evidence"] = [candidate["evidence"][0]]
        self.assertIn("EMPTY-RESULT-REASON", self.codes(example)[0])

    def test_invalid_response_is_not_repaired_and_unknown_field_not_echoed(self):
        example = self.example()
        marker = "SENSITIVE-SENTINEL-DO-NOT-ECHO"
        example["fixture_response"][marker] = marker
        original = copy.deepcopy(example)
        errors, facts = check_response(
            self.dataset.contracts,
            example["request"],
            example["fixture_response"],
            example["trusted"],
        )
        self.assertEqual(example, original)
        self.assertNotIn(marker, json.dumps(errors))
        self.assertEqual(facts, {})
        self.assertTrue(errors)

    def test_failed_execution_has_no_fabricated_coverage(self):
        report, _ = evaluate(self.dataset, self.faults)
        failed = [
            row for row in report["records"] if row["technical_outcome"] == "failed"
        ]
        self.assertEqual(len(failed), 4)
        self.assertTrue(all(row["automatic"]["facts"] == {} for row in failed))

    def test_partial_found_issue_retained_and_selected_not_partial(self):
        example = self.example("S10", "partial-found")
        original = copy.deepcopy(example["fixture_response"])
        self.assertEqual(self.codes(example)[0], set())
        self.assertEqual(example["fixture_response"], original)
        selected = self.example("S13", "selected")
        codes, facts = self.codes(selected)
        self.assertEqual(codes, set())
        self.assertEqual(facts["scope"], "selected")
        self.assertEqual(facts["coverage"]["completed"], 1)

    def test_deleted_sources_have_no_reconstructible_fixture_content(self):
        example = self.example("S12", "all-deleted")
        self.assertEqual(example["trusted"]["texts"], [])
        self.assertEqual(example["request"]["input"]["fragments"], [])
        for finding in example["request"]["input"]["findings"]:
            for link in finding["evidence"]:
                self.assertEqual(set(link), {"kind", "source_id"})
        self.assertEqual(self.codes(example)[0], set())

    def test_open_blocker_reported_without_closing_or_failing_new_answer(self):
        codes, facts = self.codes(self.example("S13", "previous-blocker"))
        self.assertEqual(codes, set())
        self.assertEqual(facts["open_prior_blockers"], 1)

    def test_strict_json_invalid_values_and_no_secret_echo(self):
        for text, expected in (
            ('{"a":1,"a":2}', "JSON-DUPLICATE-PROPERTY"),
            ('{"a":NaN}', "JSON-NONFINITE-NUMBER"),
            ('{"a":1e999}', "JSON-NONFINITE-NUMBER"),
            ('{"SENSITIVE-SENTINEL":', "JSON-UNREADABLE"),
        ):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "response.json"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(InputError) as error:
                    strict_load(path)
                self.assertEqual(str(error.exception), expected)

    def replay_mutation(self, mutate):
        replay = strict_load(self.controls)
        mutate(replay)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "replay.json"
            path.write_text(json.dumps(replay), encoding="utf-8")
            return evaluate(self.dataset, path)

    def test_dataset_request_version_and_repeated_attempt_rejected(self):
        mutations = [
            lambda r: r.update(dataset_version="unknown"),
            lambda r: r.update(dataset_sha256="changed"),
            lambda r: r["records"][0].update(request_sha256="changed"),
            lambda r: r["records"].append(r["records"][0]),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(InputError):
                self.replay_mutation(mutate)

    def test_model_mode_and_credentials_in_configuration_rejected(self):
        for mutate in (
            lambda r: r["model"].update(name="invented-real-model"),
            lambda r: r["configuration"]["generation_settings"].update(
                api_key="SENSITIVE"
            ),
            lambda r: r["records"][0].update(outcome="failed", error_code="timeout"),
        ):
            with self.subTest(mutate=mutate), self.assertRaises(InputError):
                self.replay_mutation(mutate)

    def test_response_file_cannot_escape_replay_directory(self):
        def mutate(replay):
            record = replay["records"][0]
            record.pop("response")
            record["response_file"] = "../outside.json"

        with self.assertRaisesRegex(InputError, "PATH-"):
            self.replay_mutation(mutate)

    def test_subset_experiment_shows_unscheduled_examples(self):
        report, _ = self.replay_mutation(lambda r: r.update(records=r["records"][:1]))
        self.assertEqual(report["summary"]["examples_not_scheduled"], 45)
        self.assertEqual(report["summary"]["examples_scheduled"], 1)

    def test_expert_reviews_are_bound_and_stay_provisional(self):
        _report, template = evaluate(self.dataset, self.controls)
        template["reviewer"] = "Synthetic test reviewer"
        for record in template["records"]:
            for criterion in record["criteria"] + record["claim_reviews"]:
                criterion.update(
                    verdict="uncertain",
                    rationale="Требует содержательного согласования.",
                )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "expert.json"
            path.write_text(json.dumps(template), encoding="utf-8")
            updated, _ = evaluate(self.dataset, self.controls, path)
            self.assertFalse(updated["final_model_quality_assessment"])
            self.assertEqual(updated["summary"]["expert_pending"], 0)
            self.assertEqual(
                updated["records"][0]["expert"]["criteria"][0]["verdict"], "uncertain"
            )
            template["replay_sha256"] = "wrong-run"
            path.write_text(json.dumps(template), encoding="utf-8")
            with self.assertRaisesRegex(InputError, "EXPERT-BINDING"):
                evaluate(self.dataset, self.controls, path)

    def test_reports_exclude_response_and_expert_free_text(self):
        report, _ = evaluate(self.dataset, self.controls)
        output = json.dumps(report, ensure_ascii=False) + markdown(report)
        self.assertNotIn("Хочу, чтобы выбранные", output)
        self.assertNotIn('"response":', output)
        self.assertIn("preliminary", output)

    def test_no_overwrite_reports(self):
        report, template = evaluate(self.dataset, self.controls)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new-report"
            write_report(report, template, path)
            before = (path / "report.json").read_bytes()
            with self.assertRaisesRegex(InputError, "REPORT-DIRECTORY"):
                write_report(report, template, path)
            self.assertEqual((path / "report.json").read_bytes(), before)

    def test_cli_real_exit_codes_and_safe_errors(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as stderr,
        ):
            self.assertEqual(main(["validate-dataset"]), 0)
            self.assertEqual(
                main(
                    [
                        "replay",
                        "--input",
                        str(self.controls),
                        "--output",
                        str(Path(tmp) / "controls"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "replay",
                        "--input",
                        str(self.faults),
                        "--output",
                        str(Path(tmp) / "faults"),
                    ]
                ),
                1,
            )
            self.assertEqual(
                main(
                    [
                        "replay",
                        "--input",
                        str(Path(tmp) / "missing"),
                        "--output",
                        str(Path(tmp) / "bad"),
                    ]
                ),
                2,
            )
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_deterministic_dataset_generator(self):
        result = subprocess.run(
            [sys.executable, "-B", str(HOME / "build_dataset.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS reproducible", result.stdout)

    def test_fingerprint_changes_with_input(self):
        example = self.example()
        before = digest(example["request"])
        example["request"]["input"]["segments"][0]["text"] += " Дополнение."
        self.assertNotEqual(before, digest(example["request"]))

    def test_uncertain_speech_reliability_is_inherited(self):
        example = self.example("S10", "speech-usable")
        example["request"]["input"]["segments"][0]["reliability"] = "uncertain"
        codes, facts = self.codes(example)
        self.assertEqual(codes, set())
        self.assertEqual(facts["derived_fragments"][0]["reliability"], "uncertain")

    def test_deleted_source_cannot_have_archived_text_in_trusted_fixture(self):
        example = self.example("S12", "all-deleted")
        old = copy.deepcopy(self.example()["trusted"]["texts"][0])
        old["source_ref"]["id"] = example["request"]["input"]["findings"][0][
            "evidence"
        ][0]["source_id"]
        example["trusted"]["texts"].append(old)
        codes = {
            e["code"]
            for e in check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            )
        }
        self.assertIn("DELETED-TEXT-IN-FIXTURE", codes)

    def test_compare_only_compatible_same_inputs_no_ranking(self):
        report, _ = evaluate(self.dataset, self.controls)
        other = copy.deepcopy(report)
        other["execution"]["model"]["name"] = "comparison-metadata-only"
        comparison = compare_reports(report, other)
        self.assertFalse(comparison["final_model_quality_assessment"])
        self.assertTrue(comparison["same_inputs_and_checks"])
        self.assertFalse(comparison["models_equal"])
        self.assertEqual(len(comparison["scenarios"]), 14)
        for mutate in (
            lambda r: r["records"].pop(),
            lambda r: r["dataset"].update(annotation_version="changed"),
            lambda r: r["execution"].update(tool_sha256="changed"),
        ):
            other = copy.deepcopy(report)
            mutate(other)
            with self.subTest(mutate=mutate), self.assertRaises(InputError):
                compare_reports(report, other)

    def test_expert_cannot_turn_uncertain_into_pass_by_omitting_rationale(self):
        from runner import apply_expert

        report, template = evaluate(self.dataset, self.controls)
        template["reviewer"] = "Synthetic test reviewer"
        template["records"][0]["criteria"][0]["verdict"] = "met"
        with self.assertRaisesRegex(InputError, "EXPERT-RATIONALE"):
            apply_expert(report["records"], copy.deepcopy(template), template)

    def test_independent_result_survives_a_technical_failure(self):
        def mutate(replay):
            lookup = {(r["case_id"], r["example_id"]): r for r in replay["records"]}
            success = lookup[("S10", "speech-usable")]
            failure = lookup[("S10", "independent-pdf")]
            failure.pop("response")
            failure.update(outcome="failed", error_code="timeout")
            independent = lookup[("S01", "generate")]
            replay["records"] = [success, failure, independent]

        report, _ = self.replay_mutation(mutate)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["records"][0]["automatic"]["diagnostics"], [])
        self.assertEqual(report["records"][2]["automatic"]["diagnostics"], [])

    def test_cli_compare_writes_report(self):
        report, template = evaluate(self.dataset, self.controls)
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            source = Path(tmp) / "source"
            write_report(report, template, source)
            output = Path(tmp) / "comparison"
            self.assertEqual(
                main(
                    [
                        "compare",
                        "--left",
                        str(source / "report.json"),
                        "--right",
                        str(source / "report.json"),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertTrue((output / "comparison.md").is_file())

    def test_schema_integral_numbers_are_interpreted_without_rewriting(self):
        example = self.example()
        example["request"]["input"]["segments"][0]["locator"]["start"] = 0.0
        example["fixture_response"]["result"]["fragments"][0]["occurrence"] = 0.0
        self.assertEqual(
            check_request(
                self.dataset.contracts, example["request"], example["trusted"]
            ),
            [],
        )
        original = copy.deepcopy(example)
        self.assertEqual(self.codes(example)[0], set())
        self.assertEqual(example, original)
        self.assertIsInstance(
            example["fixture_response"]["result"]["fragments"][0]["occurrence"], float
        )

    def test_semantic_fault_fixtures_remain_explicitly_for_expert(self):
        report, template = evaluate(self.dataset, self.controls)
        keys = {
            ("S09", "missed-unsupported"),
            ("S09", "false-positive"),
            ("S11", "irrelevant-evidence"),
        }
        for row in report["records"]:
            if (row["case_id"], row["example_id"]) in keys:
                self.assertEqual(row["automatic"]["diagnostics"], [])
                self.assertEqual(row["expert"]["status"], "pending")
        notes = [
            r["example_review_note"]
            for r in template["records"]
            if (r["case_id"], r["example_id"]) in keys
        ]
        self.assertEqual(len(notes), 3)
        self.assertTrue(all(notes))

    def test_revised_versions_remain_preliminary(self):
        self.assertEqual(self.dataset.manifest["dataset_version"], "1.1.0")
        self.assertEqual(self.dataset.manifest["annotation_version"], "0.2.0")
        self.assertFalse(self.dataset.manifest["semantic_gold"])
        self.assertTrue(
            all(
                c["annotation"]["status"] == "preliminary"
                for c in self.dataset.cases.values()
            )
        )
        with self.assertRaisesRegex(InputError, "REPLAY-VERSION"):
            self.replay_mutation(lambda r: r.update(annotation_version="0.1.0"))

    def test_s01_restoration_without_unsupported_mechanism(self):
        text = self.example("S01", "generate")["fixture_response"]["result"][
            "requirements"
        ][0]["text"]
        self.assertIn("восстанавливать", text)
        self.assertNotIn("кнопк", text)
        self.assertNotIn("пресет", text)
        self.assertNotIn("синхрониз", text)

    def test_s02_direct_problem_inferred_need_and_clarification(self):
        findings = self.example("S02", "extract")["fixture_response"]["result"][
            "findings"
        ]
        self.assertEqual(
            {(f["mode"], tuple(f["types"])) for f in findings},
            {("direct", ("problem",)), ("inferred", ("need",))},
        )
        example = self.example("S02", "generate")
        self.assertEqual(example["fixture_response"]["result"]["requirements"], [])
        self.assertTrue(example["fixture_response"]["questions"])
        self.assertEqual(self.codes(example)[0], set())

    def test_s03_split_preferred_combined_still_accepted(self):
        split = self.example("S03", "generate")
        combined = self.example("S03", "generate-combined")
        self.assertEqual(len(split["fixture_response"]["result"]["requirements"]), 2)
        self.assertEqual(len(combined["fixture_response"]["result"]["requirements"]), 1)
        for example in (split, combined):
            self.assertEqual(
                {c["id"] for c in example["expert_claims"]}, {"draft", "pdf"}
            )
            self.assertEqual(self.codes(example)[0], set())

    def test_s06_does_not_claim_independent_continuation(self):
        case = self.dataset.cases["S06"]
        self.assertTrue(case["coverage_notes"])
        for example in case["examples"]:
            self.assertEqual(len(example["request"]["input"]["findings"]), 2)
        self.assertNotIn(
            "независимая доработка",
            " ".join(case["annotation"]["allowed_alternatives"]),
        )

    def test_s09_severity_and_blocking_are_not_fixed_by_category(self):
        for severity in ("low", "medium", "high"):
            for blocking in (True, False):
                with self.subTest(severity=severity, blocking=blocking):
                    example = self.example("S09", "unsupported")
                    example["fixture_response"]["result"]["issues"][0].update(
                        severity=severity, blocking=blocking
                    )
                    self.assertEqual(
                        self.codes(example)[0], set()
                    )  # Appropriateness is expert-only.
        issue = self.example("S09", "unsupported")["fixture_response"]["result"][
            "issues"
        ][0]
        self.assertEqual(issue["related"], [{"origin": "input", "key": "target"}])

    def test_s12_each_claim_has_a_separate_pending_review(self):
        report, template = evaluate(self.dataset, self.controls)
        partial = next(
            r
            for r in template["records"]
            if r["case_id"] == "S12" and r["example_id"] == "partial-insufficient"
        )
        self.assertEqual(
            {c["id"] for c in partial["claim_reviews"]}, {"filters", "sync"}
        )
        self.assertTrue(
            all(c["verdict"] == "pending" for c in partial["claim_reviews"])
        )
        template["reviewer"] = "Synthetic reviewer"
        for record in template["records"]:
            for criterion in record["criteria"]:
                criterion.update(
                    verdict="uncertain",
                    rationale="Предварительное экспертное суждение.",
                )
        from runner import apply_expert

        apply_expert(report["records"], copy.deepcopy(template), template)
        partial_row = next(
            r
            for r in report["records"]
            if r["case_id"] == "S12" and r["example_id"] == "partial-insufficient"
        )
        self.assertEqual(partial_row["expert"]["status"], "pending")
        binding = copy.deepcopy(template)
        partial["claim_reviews"].pop()
        with self.assertRaisesRegex(InputError, "EXPERT-CLAIM-INVENTORY"):
            apply_expert(report["records"], binding, template)

    def test_s13_possible_duplicate_is_referred_to_a_human(self):
        example = self.example("S13", "other-proposal")
        result = example["fixture_response"]
        self.assertEqual(
            result["result"]["issues"][0]["category"], "possible_duplicate"
        )
        self.assertTrue(result["questions"])
        self.assertEqual(
            result["result"]["issues"][0]["question_ids"],
            [result["questions"][0]["local_id"]],
        )
        self.assertEqual(self.codes(example)[0], set())

    def test_intentional_semantic_errors_are_not_positive_gold(self):
        expected = {
            ("S09", "missed-unsupported"),
            ("S09", "false-positive"),
            ("S11", "irrelevant-evidence"),
        }
        actual = {
            key
            for key, example in self.dataset.examples.items()
            if example["fixture_role"] == "intentional_semantic_error"
        }
        self.assertEqual(actual, expected)
        report, template = evaluate(self.dataset, self.controls)
        for row in report["records"]:
            if (row["case_id"], row["example_id"]) in expected:
                self.assertEqual(
                    row["reference_fixture_role"], "intentional_semantic_error"
                )
                self.assertEqual(row["expert"]["status"], "pending")
        self.assertTrue(all("reference_fixture_role" in r for r in template["records"]))


if __name__ == "__main__":
    unittest.main()
