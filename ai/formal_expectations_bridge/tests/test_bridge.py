import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

import z3

from ai.formal_expectations import Limits, analyze
from ai.formal_expectations_bridge import Verification, check_pair, fingerprint, prepare
from ai.formal_expectations_bridge.synthetic import (
    base,
    catalog,
    synthetic_verifier,
    unknown_context,
)

ROOT = Path(__file__).resolve().parents[1]


class BridgeTests(unittest.TestCase):
    def verified_test_snapshot(self, data):
        """Test-local explicit approval of a particular manually constructed packet."""
        saved = deepcopy(prepare(data).packet)
        self.assertIsNotNone(saved)

        def verify(packet):
            self.assertEqual(packet, saved)
            return Verification(
                fingerprint(saved),
                "test-only-verifier",
                "Explicit exact test fixture approval",
                True,
                True,
                True,
                True,
                True,
            )

        return verify

    def test_synthetic_verifier_uses_only_authoritative_catalog(self):
        with self.assertRaises(ValueError):
            synthetic_verifier("unknown-case")
        case = deepcopy(catalog()[0])
        with self.assertRaises(ValueError):
            synthetic_verifier(case)
        case["input"]["proposal"]["atoms"][1]["values"] = {"kind": "boolean", "allowed": [True]}
        with patch("ai.formal_expectations_bridge.service.analyze") as solver:
            result = check_pair(case["input"], verify=synthetic_verifier(case["id"]))
            self.assertEqual(result.status, "blocked")
            self.assertIsNone(result.formal_result)
            solver.assert_not_called()
        case = deepcopy(next(c for c in catalog() if c["id"] == "12b-AI-false-completeness"))
        case["synthetic_confirmations"]["omega_complete_confirmed"] = True
        result = check_pair(case["input"], verify=synthetic_verifier(case["id"]))
        self.assertEqual(result.diagnostic["code"], "omega_unconfirmed")
        self.assertIsNone(result.formal_result)

    def run_case(self, case):
        verifier = (
            synthetic_verifier(case["id"]) if prepare(case["input"]).status == "prepared" else None
        )
        return check_pair(case["input"], verify=verifier)

    def test_saved_catalog_all_outcomes_and_no_expert_truth(self):
        cases = catalog()
        saved = json.loads((ROOT / "examples/cases.json").read_text(encoding="utf-8"))
        self.assertEqual(cases, saved)
        self.assertGreaterEqual(len(cases), 13)
        for case in cases:
            with self.subTest(case=case["id"]):
                result = self.run_case(case)
                self.assertEqual(result.status, case["expected_status"], result.to_dict())
                classification = (
                    result.formal_result["classification"] if result.formal_result else None
                )
                self.assertEqual(classification, case["expected_formal_class"], result.to_dict())
                self.assertEqual(result.expert_evaluation, "separate_not_computed")
                self.assertIn("conditional", result.interpretation)

    def test_expert_annotations_are_separate_preliminary_records(self):
        annotations = json.loads((ROOT / "examples/expert-review.json").read_text(encoding="utf-8"))
        self.assertEqual({a["case_id"] for a in annotations}, {c["id"] for c in catalog()})
        self.assertTrue(
            all(
                a["status"] == "PRELIMINARY"
                and a["semantic_verdict"] == "pending"
                and a["not_semantic_gold"]
                for a in annotations
            )
        )
        self.assertFalse(any("expert_evaluation" in c["input"] for c in catalog()))

    def test_exact_provenance_chain_and_versions_are_preserved(self):
        case = catalog()[0]
        result = self.run_case(case)
        packet = result.preparation
        self.assertEqual(packet["input"], case["input"])
        self.assertEqual(result.packet_sha256, fingerprint(packet))
        self.assertEqual(result.verification.packet_sha256, result.packet_sha256)
        source = packet["input"]["proposal"]["atoms"][0]["sources"][0]
        finding = packet["input"]["grouping_request"]["input"]["findings"][0]
        fragment = packet["input"]["grouping_request"]["input"]["fragments"][0]
        self.assertEqual(source["finding_ref"], finding["ref"])
        self.assertEqual(source["evidence_keys"], [fragment["key"]])
        self.assertEqual(fragment["source_ref"]["state_id"], "source-v1")
        self.assertEqual(fragment["text_ref"], fragment["source_ref"])
        self.assertEqual(packet["input"]["proposal"]["version"], "formalization-v1")
        self.assertEqual(packet["input"]["proposal"]["model"]["version"], "model-v1")
        self.assertEqual(result.solver["z3_solver_version"], "4.15.4.0")
        self.assertTrue(packet["formal_input"]["left"]["basis"].startswith("bridge-atom:"))

    def test_does_not_mutate_input_or_trust_mutated_verifier_copy(self):
        case = catalog()[0]
        original = deepcopy(case["input"])
        real_verify = synthetic_verifier(case["id"])

        def mutate(packet):
            receipt = real_verify(packet)
            packet["formal_input"]["left"]["values"]["allowed"] = [False]
            packet["input"]["proposal"]["version"] = "corrupted"
            return receipt

        result = check_pair(case["input"], verify=mutate)
        self.assertEqual(result.formal_result["classification"], "K")
        self.assertEqual(result.preparation["input"], original)
        self.assertEqual(case["input"], original)

    def test_no_formalization_and_no_verifier_never_call_z3(self):
        data = base()
        with patch("ai.formal_expectations_bridge.service.analyze") as solver:
            self.assertEqual(check_pair(data, verify=None).status, "verification_required")
            data["proposal"] = None
            result = check_pair(data, verify=lambda _: self.fail("Verifier must not run"))
            self.assertEqual(result.status, "needs_formalization")
            self.assertIsNone(result.formal_result)
            self.assertEqual(result.preparation["input"]["selection"], data["selection"])
            solver.assert_not_called()

    def test_source_state_substitution_is_rejected(self):
        data = base()
        data["proposal"]["atoms"][0]["sources"][0]["finding_ref"]["state_id"] = "latest"
        result = check_pair(data, verify=None)
        self.assertEqual(result.diagnostic["rule"], "finding_state_mismatch")
        self.assertIsNone(result.formal_result)

    def test_objects_types_and_dimensions_are_not_coerced(self):
        data = base()
        data["proposal"]["atoms"][1]["object_id"] = "other-object"
        self.assertEqual(prepare(data).diagnostic["code"], "not_comparable")
        data = base()
        data["proposal"]["atoms"][1]["values"] = {"kind": "enum", "allowed": ["true"]}
        self.assertEqual(prepare(data).diagnostic["code"], "invalid_formalization")
        data = deepcopy(next(c["input"] for c in catalog() if c["id"] == "05-parameter-aliases"))
        data["proposal"]["atoms"][1]["values"]["unit"] = "m"
        self.assertEqual(prepare(data).diagnostic["rule"], "unit_dimension_mismatch")

    def test_live_source_or_text_or_quote_or_version_change_invalidates_old_verifier(self):
        case = catalog()[0]
        for mutate in (
            lambda d: d["grouping_request"]["input"]["fragments"][0]["source_ref"].update(
                state_id="v2"
            ),
            lambda d: d["grouping_request"]["input"]["fragments"][0]["ref"].update(state_id="v2"),
            lambda d: d["proposal"].update(version="v2"),
            lambda d: d["proposal"]["model"].update(version="v2"),
            lambda d: d["grouping_request"]["input"]["findings"][0].update(text="Changed"),
        ):
            data = deepcopy(case["input"])
            mutate(data)
            result = check_pair(data, verify=synthetic_verifier(case["id"]))
            self.assertIsNone(result.formal_result)
            self.assertIn(result.status, ("rejected", "blocked"))

    def test_historical_states_are_not_replaced_by_current_states(self):
        case = catalog()[0]
        # No API/store lookup occurs. A verifier may accept a permitted exact historical
        # snapshot, or reject it as unavailable; the bridge never chooses a newer state.
        result = self.run_case(case)
        self.assertEqual(
            result.preparation["input"]["proposal"]["atoms"][0]["sources"][0]["finding_ref"][
                "state_id"
            ],
            "f1-v1",
        )
        denied = check_pair(
            case["input"],
            verify=lambda p: replace(synthetic_verifier(case["id"])(p), basis_verified=False),
        )
        self.assertEqual(denied.status, "blocked")
        self.assertIsNone(denied.formal_result)

    def test_foreign_and_deleted_and_uncertain_evidence(self):
        data = base()
        data["proposal"]["atoms"][0]["sources"][0]["evidence_keys"] = ["e2"]
        self.assertEqual(prepare(data).diagnostic["code"], "basis_unavailable")
        data = base()
        data["grouping_request"]["input"]["findings"][0]["evidence"] = [
            {"kind": "deleted_source", "source_id": "source1"}
        ]
        data["grouping_request"]["input"]["fragments"] = data["grouping_request"]["input"][
            "fragments"
        ][1:]
        self.assertEqual(prepare(data).diagnostic["code"], "basis_unavailable")
        data = base()
        data["grouping_request"]["input"]["fragments"][0]["reliability"] = "uncertain"
        self.assertEqual(prepare(data).diagnostic["rule"], "unreliable_evidence")

    def test_tampered_and_untyped_receipts(self):
        case = catalog()[0]
        valid = synthetic_verifier(case["id"])
        callbacks = [
            lambda p: True,
            lambda p: asdict(valid(p)),
            lambda p: replace(valid(p), packet_sha256="wrong"),
            lambda p: replace(valid(p), basis_verified="true"),
            lambda p: replace(valid(p), verifier_id=""),
            lambda p: replace(valid(p), justification=""),
        ]
        for callback in callbacks:
            with self.subTest(callback=callback):
                result = check_pair(case["input"], verify=callback)
                self.assertEqual(result.status, "blocked")
                self.assertIsNone(result.formal_result)

    def test_all_trusted_confirmations_are_required(self):
        case = next(c for c in catalog() if c["id"] == "04-incomplete-information")
        for field in (
            "basis_verified",
            "formalization_confirmed",
            "comparability_confirmed",
            "contexts_confirmed",
            "omega_complete_confirmed",
        ):
            with self.subTest(field=field):
                result = check_pair(
                    case["input"],
                    verify=lambda p, field=field: replace(
                        synthetic_verifier(case["id"])(p), **{field: False}
                    ),
                )
                self.assertEqual(result.status, "blocked")
                self.assertIsNone(result.formal_result)

    def test_AI_cannot_approve_its_own_incomplete_omega(self):
        case = next(c for c in catalog() if c["id"] == "12b-AI-false-completeness")
        prepared = prepare(case["input"])
        self.assertEqual(analyze(prepared.packet["formal_input"]).classification, "K")
        result = self.run_case(case)
        self.assertEqual(result.diagnostic["code"], "omega_unconfirmed")
        self.assertIsNone(result.formal_result)
        # With a receipt for the genuinely complete case, removing a variant also fails.
        complete = next(c for c in catalog() if c["id"] == "04-incomplete-information")
        forged = check_pair(case["input"], verify=synthetic_verifier(complete["id"]))
        self.assertIsNone(forged.formal_result)

    def test_wrong_formalization_can_be_solver_valid_but_is_not_published(self):
        for key, structural_class in (("10-false-K", "K"), ("11-false-D", "D")):
            case = next(c for c in catalog() if c["id"] == key)
            self.assertEqual(
                analyze(prepare(case["input"]).packet["formal_input"]).classification,
                structural_class,
            )
            with patch("ai.formal_expectations_bridge.service.analyze") as solver:
                self.assertIsNone(self.run_case(case).formal_result)
                solver.assert_not_called()

    def test_position_with_multiple_findings_is_not_silently_reduced(self):
        case = next(c for c in catalog() if c["id"] == "15-multiple-position-findings")
        result = self.run_case(case)
        self.assertEqual(len(result.preparation["input"]["proposal"]["atoms"][0]["sources"]), 2)
        data = deepcopy(case["input"])
        data["selection"]["left_finding_keys"] = ["f1"]
        self.assertEqual(
            prepare(data).diagnostic["rule"], "position_members_must_be_explicit_and_complete"
        )
        data = deepcopy(case["input"])
        data["proposal"]["atoms"][0]["sources"] = data["proposal"]["atoms"][0]["sources"][:1]
        self.assertEqual(prepare(data).diagnostic["rule"], "unaccounted_position_finding")
        data["proposal"]["omissions"] = [
            {
                "finding_key": "f3",
                "reason": "Explicitly compare f1/f2 only; no class for the entire position.",
            }
        ]
        self.assertEqual(prepare(data).status, "prepared")

    def test_decomposition_keeps_unselected_wishes_and_can_select_same_finding_pair(self):
        case = next(c for c in catalog() if c["id"] == "07-multiple-wishes")
        result = self.run_case(case)
        self.assertEqual(result.preparation["unselected_atom_ids"], ["a3"])
        data = deepcopy(case["input"])
        data["selection"].update(conflict=None, left_finding_keys=["f1"], right_finding_keys=["f1"])
        data["proposal"]["atoms"] = [a for a in data["proposal"]["atoms"] if a["id"] != "a2"]
        data["proposal"]["pair"]["right_atom_id"] = "a3"
        new_case = {**case, "input": data}
        result = check_pair(data, verify=self.verified_test_snapshot(new_case["input"]))
        self.assertEqual(result.formal_result["classification"], "D")

    def test_absence_of_model_conflict_does_not_prevent_explicit_pair(self):
        case = catalog()[0]
        data = deepcopy(case["input"])
        data["grouping_response"]["result"]["groups"][0]["conflicts"] = []
        data["selection"]["conflict"] = None
        result = check_pair(data, verify=self.verified_test_snapshot(data))
        self.assertEqual(result.formal_result["classification"], "K")

    def test_unsupported_or_ambiguous_context_models(self):
        data = unknown_context()
        data["proposal"]["model"]["relations"] = []
        self.assertEqual(prepare(data).diagnostic["code"], "unsupported_context")
        data = unknown_context()
        data["proposal"]["model"]["relations"][0]["relation"] = "unknown"
        self.assertEqual(prepare(data).diagnostic["rule"], "context_relation_unresolved")
        data = base()
        data["proposal"]["atoms"][0]["values"]["depends_on"] = "context"
        self.assertEqual(prepare(data).status, "rejected")

    def test_unknowns_and_incomplete_context_never_turn_into_universal_or_U(self):
        data = unknown_context()
        data["proposal"]["omega"] = None
        result = check_pair(data, verify=None)
        self.assertEqual(result.status, "needs_refinements")
        self.assertIsNone(result.preparation["formal_input"]["left"]["conditions"])
        data = unknown_context()
        data["proposal"]["omega"]["declared_complete"] = False
        self.assertEqual(check_pair(data, verify=None).status, "needs_refinements")
        data = base()
        data["grouping_response"]["coverage"][0].update(
            disposition="insufficient_information", reason="Недостаточно сведений"
        )
        result = check_pair(data, verify=None)
        self.assertIsNone(result.formal_result)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.diagnostic["code"], "context_incomplete")

    def test_known_data_cannot_be_changed_by_refinement(self):
        data = unknown_context()
        data["proposal"]["omega"]["variants"][1]["left"]["values"] = {
            "kind": "boolean",
            "allowed": [False],
        }
        self.assertEqual(prepare(data).diagnostic["rule"], "refinement_changes_known_data")

    def test_no_technical_failure_becomes_semantic_U(self):
        case = catalog()[0]
        for reason, code in (("timeout", "timeout"), ("unknown theory", "solver_unknown")):
            with (
                patch("ai.formal_expectations.solver.z3.Solver.check", return_value=z3.unknown),
                patch(
                    "ai.formal_expectations.solver.z3.Solver.reason_unknown", return_value=reason
                ),
            ):
                result = self.run_case(case)
                self.assertEqual(result.status, "formal_failure")
                self.assertIsNone(result.formal_result["classification"])
                self.assertEqual(result.formal_result["diagnostic"]["code"], code)
        result = check_pair(
            case["input"], verify=synthetic_verifier(case["id"]), limits=Limits(solver_rlimit=1)
        )
        self.assertIsNone(result.formal_result["classification"])
        self.assertEqual(result.formal_result["diagnostic"]["code"], "resource_limit")

    def test_no_input_may_provide_verification_receipt(self):
        data = base()
        data["verification"] = {"basis_verified": True}
        self.assertEqual(prepare(data).status, "rejected")

    def test_invalid_json_and_limits_and_no_code_execution(self):
        for raw in ("{", '{"x":1,"x":2}', b"\xff", "NaN", "[]"):
            self.assertEqual(prepare(raw).status, "rejected")
        self.assertEqual(
            prepare(base(), limits=Limits(max_input_bytes=10)).diagnostic["code"], "resource_limit"
        )
        data = base()
        data["proposal"]["atoms"][0]["values"] = {
            "kind": "python",
            "code": "__import__('os').system('false')",
        }
        self.assertEqual(prepare(data).status, "rejected")
        data = base()
        data["proposal"]["atoms"][0]["missing_fields"] = ["conditions"]
        self.assertEqual(prepare(data).diagnostic["rule"], "missing_information_must_be_explicit")

    def test_verifier_failure_is_sanitized(self):
        def bad(_):
            raise RuntimeError("SECRET_SOURCE_TEXT")

        result = check_pair(base(), verify=bad)
        self.assertEqual(result.status, "blocked")
        self.assertNotIn("SECRET_SOURCE_TEXT", json.dumps(result.diagnostic))

    def test_pairwise_S_is_not_global_verdict(self):
        triples = [c for c in catalog() if c["id"].startswith("13-")]
        self.assertEqual(len(triples), 3)
        for case in triples:
            result = self.run_case(case)
            self.assertEqual(result.formal_result["classification"], "S")
            self.assertNotIn("global_classification", result.to_dict())
        self.assertFalse({"a", "b"} & {"b", "c"} & {"a", "c"})

    def test_CLI_synthetic_demo_and_preparation_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "prepared-input.json"
            input_file.write_text(json.dumps(base()), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "ai.formal_expectations_bridge",
                    "prepare",
                    str(input_file),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            preparation = json.loads(process.stdout)
            self.assertEqual(preparation["status"], "prepared")
            self.assertNotIn("formal_result", preparation)
        for key, classification in (
            ("01-direct-conflict", "K"),
            ("04-incomplete-information", "U"),
        ):
            process = subprocess.run(
                [sys.executable, "-B", "-m", "ai.formal_expectations_bridge", "demo", key],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            output = json.loads(process.stdout)
            self.assertTrue(output["synthetic"])
            self.assertEqual(output["result"]["formal_result"]["classification"], classification)
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "ai.formal_expectations_bridge",
                "demo",
                "12b-AI-false-completeness",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIsNone(json.loads(process.stdout)["result"]["formal_result"])


if __name__ == "__main__":
    unittest.main()
