import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import z3
from ai.formal_expectations import Limits
from ai.formal_expectations_bridge import fingerprint
from jsonschema import Draft202012Validator

from experiments.qwen_z3.dataset import applicability, export, get_case, load_cases
from experiments.qwen_z3.prompt import task
from experiments.qwen_z3.protocol import (
    SCHEMA_PATH,
    ExperimentError,
    canonical,
    input_view,
    response_from_reference,
    sha,
)
from experiments.qwen_z3.review import validate_review
from experiments.qwen_z3.runner import (
    SYNTHETIC_MODEL,
    collect,
    evaluate,
    generate_synthetic,
    replay,
    summarize,
    write,
)
from experiments.qwen_z3.schema import SCHEMA


class PipelineTests(unittest.TestCase):
    def test_collect_preflights_bounded_selection_before_reading(self):
        case, _ = self.proposal()
        selections = (
            (iter([case["id"]] * 257), 1),
            (iter([case["id"], case["id"]]), 1),
            (iter([]), 1),
            (iter(["unknown-case"]), 1),
            (iter([case["id"]]), True),
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            for selected, attempt in selections:
                with patch("experiments.qwen_z3.runner._read") as reader:
                    with self.assertRaises(ExperimentError):
                        collect("missing", "missing", output, case_ids=selected, attempt=attempt)
                    reader.assert_not_called()
                self.assertFalse(output.exists())

    def test_invalid_review_does_not_hide_primary_syntax_failure(self):
        case, value = self.proposal()
        _, review, _ = self.evaluated(case, value)
        row, _, _ = evaluate(case, b"{", SYNTHETIC_MODEL, review=review)
        self.assertEqual(row["status"], "syntax_error")
        self.assertEqual(row["diagnostic"]["category"], "syntax_error")
        self.assertEqual(row["review_diagnostic"]["category"], "review_error")
        self.assertIsNone(row["formal_result"])

    def test_registered_negative_formalization_proposals_remain_unapproved(self):
        from experiments.qwen_z3.controls import negative_controls

        for index, control in enumerate(negative_controls()):
            row, form, packet = evaluate(
                get_case(control["case_id"]),
                control["raw"],
                SYNTHETIC_MODEL,
                attempt=index + 2,
                synthetic=True,
            )
            self.assertEqual(row["status"], control["expected"], control["label"])
            self.assertIsNone(row["formal_result"])

    def proposal(self, key="B-01-direct-conflict"):
        case = get_case(key)
        return case, response_from_reference(case)

    def evaluated(self, case, value, **kwargs):
        return evaluate(case, canonical(value), deepcopy(SYNTHETIC_MODEL), **kwargs)

    def accepted_review(self, case, value):
        # Test-only simulation of an explicit independent human review, not a CLI
        # auto-approval helper. Every binding comes from this particular raw input.
        _, form, _ = self.evaluated(case, value)
        form["reviewer"] = "test-expert"
        for item in form["criteria"].values():
            item.update(
                verdict="accepted", rationale="Explicit test expert assessment of this snapshot."
            )
        return form

    def test_schema_snapshot_and_all_registered_controls(self):
        saved = json.loads(SCHEMA_PATH.read_text())
        self.assertEqual(saved, SCHEMA)
        Draft202012Validator.check_schema(saved)
        self.assertEqual(len(load_cases()), 22)
        observed = set()
        for case in load_cases():
            value = response_from_reference(case)
            row, form, packet = self.evaluated(case, value, synthetic=True)
            with self.subTest(case=case["id"]):
                if case["expected_formal_class"] is not None:
                    self.assertEqual(row["status"], "formal_conclusion", row)
                    self.assertEqual(
                        row["formal_result"]["classification"], case["expected_formal_class"]
                    )
                    observed.add(row["formal_result"]["classification"])
                else:
                    self.assertIn(row["status"], ("model_abstained", "incomplete_omega"))
                    self.assertIsNone(row["formal_result"])
                self.assertIsNone(row["semantic_accuracy"])
                self.assertTrue(all(c["verdict"] == "pending" for c in form["criteria"].values()))
        self.assertEqual(observed, {"D", "K", "S", "U"})

    def test_S01_S14_applicability_is_explicit(self):
        inventory = applicability()
        self.assertEqual(len(inventory), 14)
        self.assertEqual(
            {r["case_id"] for r in inventory if r["status"] == "included"}, {"S05", "S06"}
        )
        self.assertEqual(sum(len(r["applicable_examples"]) for r in inventory), 3)
        self.assertNotIn("reference", input_view(load_cases()[0]))

    def test_proposals_never_authorize_themselves(self):
        case, value = self.proposal()
        with patch("experiments.qwen_z3.runner.check_pair") as solver:
            row, form, packet = self.evaluated(case, value)
            self.assertEqual(row["status"], "review_required")
            self.assertIsNone(row["formal_result"])
            self.assertEqual(packet["input"]["proposal"]["origin"]["kind"], "ai")
            self.assertEqual(form["binding"]["packet_sha256"], fingerprint(packet))
            solver.assert_not_called()

    def test_forbidden_trust_fields_and_origin_rejected(self):
        for location in ("root", "formalization", "omega_origin"):
            case, value = self.proposal("B-04-incomplete-information")
            if location == "root":
                value["basis_verified"] = True
            elif location == "formalization":
                value["formalization"]["formalization_confirmed"] = True
            else:
                value["formalization"]["omega"]["origin"] = {"kind": "human"}
            row, _, _ = self.evaluated(case, value, synthetic=True)
            self.assertEqual(row["status"], "structure_error")
            self.assertIsNone(row["formal_result"])

    def test_syntax_and_structure_are_separate_and_no_repair(self):
        case, value = self.proposal()
        for raw in (
            b"{",
            b'{"x":1,"x":2}',
            b"NaN",
            b"\xff",
            b"```json\n{}\n```",
            b"<think>reason</think>{}",
        ):
            row, _, _ = evaluate(case, raw, SYNTHETIC_MODEL)
            self.assertEqual(row["status"], "syntax_error")
            self.assertEqual(row["raw_sha256"], sha(raw))
        for raw in (b"[]", b"{}", b"1.5"):
            row, _, _ = evaluate(case, raw, SYNTHETIC_MODEL)
            self.assertEqual(row["status"], "structure_error")
        value["formalization"]["atoms"][0]["values"] = {
            "kind": "interval",
            "lower": 1.5,
            "upper": 3,
            "unit": "s",
        }
        self.assertEqual(self.evaluated(case, value)[0]["status"], "structure_error")

    def test_provenance_and_complete_position_scope(self):
        case, value = self.proposal("B-15-multiple-position-findings")
        for change in ("hash", "member", "finding_state", "evidence"):
            bad = deepcopy(value)
            if change == "hash":
                bad["input_sha256"] = "0" * 64
            elif change == "member":
                bad["selection"]["left_finding_keys"] = ["f1"]
            elif change == "finding_state":
                bad["formalization"]["atoms"][0]["sources"][0]["finding_ref"]["state_id"] = (
                    "current-not-selected"
                )
            else:
                bad["formalization"]["atoms"][0]["sources"][0]["evidence_keys"] = ["e2"]
            with self.subTest(change=change):
                row, _, _ = self.evaluated(case, bad)
                self.assertEqual(row["status"], "provenance_error", row)
                self.assertIsNone(row["formal_result"])

    def test_false_K_and_D_are_not_silently_corrected(self):
        for key, change in (
            ("B-10-false-K", "values"),
            ("B-02-different-conditions", "conditions"),
        ):
            case, value = self.proposal(key)
            original = deepcopy(value)
            if change == "values":
                value["formalization"]["atoms"][1]["values"]["allowed"] = [False]
            else:
                value["formalization"]["atoms"][1]["context_id"] = value["formalization"]["atoms"][
                    0
                ]["context_id"]
            raw = canonical(value)
            row, form, packet = evaluate(case, raw, SYNTHETIC_MODEL, synthetic=True)
            self.assertEqual(row["status"], "review_required")
            self.assertIsNone(row["formal_result"])
            self.assertTrue(row["reference_difference_paths"])
            self.assertNotEqual(value, original)
            self.assertEqual(row["raw_sha256"], sha(raw))
            form["reviewer"] = "independent-test-expert"
            form["criteria"]["values_grounded"].update(
                verdict="rejected",
                rationale="The proposed fact is not supported by the selected source.",
            )
            denied, _, _ = evaluate(case, raw, SYNTHETIC_MODEL, review=form)
            self.assertEqual(denied["status"], "semantic_error")
            self.assertIsNone(denied["formal_result"])

    def test_parameter_mismatch_and_invented_numeric_value(self):
        case, value = self.proposal("B-05-parameter-aliases")
        bad = deepcopy(value)
        bad["formalization"]["atoms"][1]["parameter_id"] = "other_parameter"
        self.assertEqual(self.evaluated(case, bad)[0]["status"], "formalization_error")
        value["formalization"]["atoms"][0]["values"]["lower"] = "2"
        row, _, packet = self.evaluated(case, value, synthetic=True)
        self.assertEqual(row["status"], "review_required")
        self.assertEqual(packet["formal_input"]["left"]["values"]["lower"], "2")

    def test_decimal_schema_and_exact_units_through_bridge(self):
        case, value = self.proposal("B-05-parameter-aliases")
        value["formalization"]["atoms"][0]["values"].update(lower="1.1", upper="3.0")
        value["formalization"]["atoms"][1]["values"].update(lower="3000", upper="3500", unit="ms")
        row, form, packet = self.evaluated(case, value)
        self.assertEqual(row["status"], "review_required", row)
        self.assertEqual(packet["formal_input"]["left"]["values"]["lower"], "1.1")
        row, _, _ = self.evaluated(case, value, review=self.accepted_review(case, value))
        self.assertEqual(row["formal_result"]["classification"], "S")
        value["formalization"]["atoms"][0]["values"]["lower"] = "1\\x1"
        self.assertEqual(self.evaluated(case, value)[0]["status"], "structure_error")

    def test_symlink_response_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = generate_synthetic(root / "inputs")
            manifest["records"] = manifest["records"][:1]
            (root / "outside.json").write_bytes(b"{}")
            (root / "inputs/link.json").symlink_to(root / "outside.json")
            manifest["records"][0].update(response_file="link.json", response_sha256=sha(b"{}"))
            (root / "inputs/manifest.json").write_bytes(canonical(manifest))
            with self.assertRaises(ExperimentError):
                replay(root / "inputs/manifest.json", root / "out")

    def test_AI_claimed_complete_omega_requires_review(self):
        case, value = self.proposal("B-04-incomplete-information")
        value["formalization"]["omega"]["variants"] = value["formalization"]["omega"]["variants"][
            :1
        ]
        row, form, _ = self.evaluated(case, value, synthetic=True)
        self.assertEqual(row["status"], "review_required")
        form["reviewer"] = "test-expert"
        form["criteria"]["omega_completeness"].update(
            verdict="uncertain", rationale="A second admissible case was omitted."
        )
        row, _, _ = self.evaluated(case, value, review=form)
        self.assertEqual(row["status"], "unconfirmed_omega")
        self.assertIsNone(row["formal_result"])

    def test_pending_review_does_not_approve_unknowns(self):
        case, value = self.proposal("B-04-incomplete-information")
        row, form, _ = self.evaluated(case, value)
        row, _, _ = self.evaluated(case, value, review=form)
        self.assertEqual(row["status"], "review_required")
        self.assertIsNone(row["formal_result"])
        value["formalization"]["omega"]["declared_complete"] = False
        self.assertEqual(self.evaluated(case, value)[0]["status"], "incomplete_omega")

    def test_explicit_accepted_human_review_calls_existing_Z3(self):
        case, value = self.proposal()
        form = self.accepted_review(case, value)
        row, _, _ = self.evaluated(case, value, review=form)
        self.assertEqual(row["status"], "formal_conclusion", row)
        self.assertEqual(row["formal_result"]["classification"], "K")
        self.assertEqual(row["applied_review_sha256"], fingerprint(form))
        self.assertIsNone(row["semantic_accuracy"])

    def test_review_is_bound_to_raw_bytes_model_attempt_and_packet(self):
        case, value = self.proposal()
        form = self.accepted_review(case, value)
        for change in ("raw", "model", "attempt", "packet", "dataset"):
            model, raw, attempt, review = (
                deepcopy(SYNTHETIC_MODEL),
                canonical(value),
                1,
                deepcopy(form),
            )
            if change == "raw":
                raw += b"\n"
            elif change == "model":
                model["revision"] = "another-digest"
            elif change == "attempt":
                attempt = 2
            elif change == "packet":
                review["binding"]["packet_sha256"] = "0" * 64
            else:
                review["binding"]["dataset_sha256"] = "0" * 64
            row, _, _ = evaluate(case, raw, model, attempt=attempt, review=review)
            self.assertEqual(row["status"], "review_error", change)
            self.assertIsNone(row["formal_result"])
        review = deepcopy(form)
        review["binding"]["attempt"] = True
        with self.assertRaises(ExperimentError):
            validate_review(review, form["binding"])

    def test_forged_review_identity_criteria_and_notes(self):
        case, value = self.proposal()
        form = self.accepted_review(case, value)
        for change in ("identity", "kind", "criteria", "notes", "reference"):
            bad = deepcopy(form)
            if change == "identity":
                bad["reviewer"] = None
            elif change == "kind":
                bad["reviewer_kind"] = "ai"
            elif change == "criteria":
                bad["criteria"]["basis_verified"] = {
                    "verdict": "accepted",
                    "rationale": "self approved",
                }
            elif change == "notes":
                bad["criteria"]["conditions"]["rationale"] = ""
            else:
                bad["reference_status"] = "APPROVED_SEMANTIC_GOLD"
            self.assertEqual(self.evaluated(case, value, review=bad)[0]["status"], "review_error")

    def test_synthetic_mode_cannot_approve_arbitrary_snapshots(self):
        case, value = self.proposal()
        for change in ("model", "bytes", "attempt", "value"):
            model, raw, attempt = deepcopy(SYNTHETIC_MODEL), canonical(value), 1
            if change == "model":
                model["parameters"]["seed"] = False
            elif change == "bytes":
                raw += b" "
            elif change == "attempt":
                attempt = 2
            else:
                changed = deepcopy(value)
                changed["formalization"]["atoms"][1]["values"]["allowed"] = [True]
                raw = canonical(changed)
            row, _, _ = evaluate(case, raw, model, attempt=attempt, synthetic=True)
            self.assertEqual(row["status"], "review_required", change)
            self.assertIsNone(row["formal_result"])

    def test_solver_timeout_unknown_resource_are_not_U(self):
        case, value = self.proposal()
        form = self.accepted_review(case, value)
        for reason, code in (("timeout", "timeout"), ("incomplete theory", "solver_unknown")):
            with (
                patch("ai.formal_expectations.solver.z3.Solver.check", return_value=z3.unknown),
                patch(
                    "ai.formal_expectations.solver.z3.Solver.reason_unknown", return_value=reason
                ),
            ):
                row, _, _ = self.evaluated(case, value, review=form)
                self.assertEqual(row["status"], "z3_technical_error")
                self.assertEqual(row["formal_result"]["diagnostic"]["code"], code)
                self.assertIsNone(row["formal_result"]["classification"])
        row, _, _ = self.evaluated(case, value, review=form, limits=Limits(solver_rlimit=1))
        self.assertEqual(row["status"], "z3_technical_error")
        self.assertIsNone(row["formal_result"]["classification"])

    def test_summary_keeps_expert_denominators_and_accuracy_unset(self):
        case, value = self.proposal()
        row, _, _ = self.evaluated(case, value)
        summary = summarize([row])
        self.assertIsNone(summary["semantic_accuracy"])
        self.assertEqual(summary["requires_clarification_fraction"], 1)
        self.assertEqual(summary["joint_expert_comparisons"]["false_K"]["unreviewed"], 1)

    def test_export_separates_inputs_and_references_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "export"
            export(out)
            inputs = json.loads((out / "inputs.json").read_text())
            references = json.loads((out / "references.json").read_text())
            self.assertEqual(len(inputs["cases"]), 22)
            self.assertNotIn("reference", inputs["cases"][0])
            self.assertFalse(references["semantic_gold"])
            with self.assertRaises(FileExistsError):
                export(out)

    def test_task_hides_references_and_collect_preserves_model_content(self):
        case, value = self.proposal()
        exported = task(case)
        self.assertNotIn("reference", exported["input"])
        self.assertNotIn("expected_formal_class", exported["input"])
        self.assertEqual(exported["prompt_version"], "qwen-z3/1")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "responses").mkdir()
            raw = canonical(value) + b"\n"
            (root / "responses" / (case["id"] + ".json")).write_bytes(raw)
            model = deepcopy(SYNTHETIC_MODEL)
            model["name"] = "qwen-saved-test"
            write(root / "model.json", model)
            collect(root / "responses", root / "model.json", root / "packed", case_ids=[case["id"]])
            self.assertEqual((root / "packed/000.bin").read_bytes(), raw)
            report = replay(root / "packed/manifest.json", root / "review")
            self.assertEqual(report["records"][0]["status"], "review_required")
            self.assertFalse(report["inference_performed_by_this_tool"])

    def test_replay_preserves_raw_and_approved_review_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_synthetic(root / "inputs")
            report = replay(root / "inputs/manifest.json", root / "first")
            self.assertEqual(len(report["records"]), 22)
            self.assertEqual(report["summary"]["statuses"]["formal_conclusion"], 19)
            self.assertFalse(report["inference_performed_by_this_tool"])
            self.assertEqual(
                (root / "inputs/000.json").read_bytes(), (root / "first/raw/000.bin").read_bytes()
            )
            with self.assertRaises(FileExistsError):
                replay(root / "inputs/manifest.json", root / "first")

    def test_saved_model_mode_stays_pending_until_external_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = generate_synthetic(root / "inputs")
            manifest.update(mode="saved_model_proposals", records=manifest["records"][:1])
            manifest["model"]["name"] = "qwen-test-saved-not-real-inference"
            (root / "inputs/manifest.json").write_bytes(canonical(manifest))
            first = replay(root / "inputs/manifest.json", root / "pending")
            self.assertEqual(first["records"][0]["status"], "review_required")
            registry = json.loads((root / "pending/reviews.json").read_text())
            form = registry["reviews"][0]
            form["reviewer"] = "independent-test-expert"
            for criterion in form["criteria"].values():
                criterion.update(
                    verdict="accepted", rationale="Exact saved response inspected in test."
                )
            write(root / "accepted.json", registry)
            approved = replay(
                root / "inputs/manifest.json",
                root / "approved",
                reviews_path=root / "accepted.json",
            )
            self.assertEqual(approved["records"][0]["status"], "formal_conclusion")
            self.assertEqual(
                (root / "accepted.json").read_bytes(),
                (root / "approved/applied-reviews.bin").read_bytes(),
            )

    def test_invalid_raw_still_preserved_with_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = generate_synthetic(root / "inputs")
            manifest["records"] = manifest["records"][:1]
            raw = b'{"unclosed"'
            (root / "inputs/000.json").write_bytes(raw)
            manifest["records"][0]["response_sha256"] = sha(raw)
            (root / "inputs/manifest.json").write_bytes(canonical(manifest))
            report = replay(root / "inputs/manifest.json", root / "out")
            self.assertEqual(report["records"][0]["status"], "syntax_error")
            self.assertEqual((root / "out/raw/000.bin").read_bytes(), raw)

    def test_rejects_path_escape_stale_dataset_hash_and_duplicate_attempt(self):
        for change in ("path", "dataset", "hash", "duplicate", "synthetic_identity"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = generate_synthetic(root / "inputs")
                manifest["records"] = manifest["records"][:1]
                if change == "path":
                    (root / "outside.json").write_bytes(b"{}")
                    manifest["records"][0]["response_file"] = "../outside.json"
                elif change == "dataset":
                    manifest["dataset_sha256"] = "0" * 64
                elif change == "hash":
                    manifest["records"][0]["response_sha256"] = "0" * 64
                elif change == "duplicate":
                    manifest["records"] *= 2
                else:
                    manifest["model"]["parameters"]["seed"] = False
                (root / "inputs/manifest.json").write_bytes(canonical(manifest))
                with self.assertRaises(ExperimentError):
                    replay(root / "inputs/manifest.json", root / "out")
                self.assertFalse((root / "out").exists())

    def test_CLI_end_to_end_inventory_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:

            def run(*args):
                return subprocess.run(
                    [sys.executable, "-B", "-m", "experiments.qwen_z3", *args],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )

            self.assertEqual(json.loads(run("inventory").stdout)["cases"], 22)
            root = Path(directory)
            self.assertEqual(run("synthetic", "--output", str(root / "inputs")).returncode, 0)
            result = run(
                "replay",
                "--manifest",
                str(root / "inputs/manifest.json"),
                "--output",
                str(root / "out"),
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)["records"], 22)
            again = run(
                "replay",
                "--manifest",
                str(root / "inputs/manifest.json"),
                "--output",
                str(root / "out"),
            )
            self.assertEqual(again.returncode, 2)


if __name__ == "__main__":
    unittest.main()
