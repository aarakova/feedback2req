"""Verification acceptance regressions and synthetic controls, not semantic evals."""

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import URLError

from jsonschema import Draft202012Validator

from ai.verify_requirement import (
    ReviewPlan,
    VerificationError,
    validate_request,
    validate_response,
    verify_requirement,
)
from ai.verify_requirement.prompt import SYSTEM_PROMPT
from ai.verify_requirement.provider import Ollama, OllamaConfig, Replay
from ai.verify_requirement.validation import ASSESSMENTS, decode, response_format
from evals.ai.verification.build_cases import (
    artifacts,
    assessment,
    cases,
    semantic_counterexamples,
)

ROOT = Path(__file__).resolve().parents[2]


def plan(row):
    raw = row.get("review_plan")
    return (
        None
        if raw is None
        else ReviewPlan(
            frozenset(raw["checked_assessments"]), frozenset(raw["comparison_keys"])
        )
    )


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.rows = {c["id"]: c for c in cases()}
        self.req = deepcopy(self.rows["supported"]["request"])
        self.resp = deepcopy(self.rows["supported"]["response"])

    def assert_bad(self, rule, req=None, resp=None, review_plan=None):
        with self.assertRaises(VerificationError) as caught:
            validate_response(
                self.req if req is None else req,
                self.resp if resp is None else resp,
                review_plan=review_plan,
            )
        self.assertEqual(caught.exception.rule, rule)

    def test_all_controls(self):
        for name, row in self.rows.items():
            with self.subTest(case=name):
                self.assertEqual(
                    validate_response(
                        row["request"], row["response"], review_plan=plan(row)
                    ),
                    row["response"],
                )

    def test_artifacts_reproducible(self):
        for name, value in artifacts().items():
            self.assertEqual(
                (ROOT / "evals/ai/verification" / name).read_text("utf-8"),
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            )

    def test_all_approved_verify_requests(self):
        for path in (ROOT / "docs/contracts/ai/examples").glob("verify*.request.json"):
            with self.subTest(name=path.name):
                validate_request(json.loads(path.read_text("utf-8")))

    def test_self_contained_schema(self):
        schema = response_format()
        Draft202012Validator(schema).validate(self.resp)
        self.assertIn("CheckAssessment", schema["$defs"])
        self.assertNotIn("RequirementCandidate", schema["$defs"])
        self.assertNotIn(
            "https://feedback2req.invalid/contracts/ai/v1/common.schema.json#",
            json.dumps(schema),
        )

    def test_exactly_four_kinds(self):
        self.resp["result"]["checks"][1]["kind"] = "support"
        self.assert_bad("schema")
        self.resp["result"]["checks"].pop()
        self.assert_bad("schema")

    def test_review_defect_unreviewed_issues_even_with_empty_considered(self):
        row = self.rows["contradiction"]
        row["response"]["coverage"][0].update(
            reviewed=False, disposition="not_processed", reason="Не рассмотрено."
        )
        for check in row["response"]["result"]["checks"]:
            check["considered_keys"] = []
        self.assert_bad("unreviewed_issues", row["request"], row["response"])

    def test_not_processed_is_not_clean(self):
        self.resp["coverage"][0].update(
            reviewed=False, disposition="not_processed", reason="Не рассмотрено."
        )
        self.assert_bad("unreviewed_assessment")

    def test_coverage_target_and_closed_fields(self):
        self.resp["coverage"][0]["input_key"] = "f1"
        self.assert_bad("coverage_target")
        self.resp["coverage"][0]["input_key"] = "target"
        for field in ("approved", "rejected", "is_open", "resolution", "passed"):
            response = deepcopy(self.resp)
            response[field] = True
            self.assert_bad("schema", resp=response)

    def test_target_must_be_considered(self):
        assessment(self.resp, "support")["considered_keys"].remove("target")
        self.assert_bad("check_target_not_considered")

    def test_insufficient_information_cannot_claim_all_clean(self):
        self.resp["coverage"][0].update(
            disposition="insufficient_information", reason="Сведений не хватает."
        )
        self.assert_bad("insufficient_clean_result")

    def test_partial_requires_independent_plan_and_preserves_found_issue(self):
        row = self.rows["partial-found"]
        self.assert_bad("partial_plan_required", row["request"], row["response"])
        accepted = validate_response(
            row["request"], row["response"], review_plan=plan(row)
        )
        self.assertTrue(accepted["result"]["issues"])
        self.assertEqual(accepted["coverage"][0]["disposition"], "partially_processed")

    def test_false_completed_cannot_bypass_trusted_plan(self):
        row = self.rows["partial-found"]
        row["response"]["coverage"][0]["disposition"] = "completed"
        self.assert_bad(
            "plan_coverage_mismatch", row["request"], row["response"], plan(row)
        )

    def test_incomplete_duplicates_cannot_be_clean(self):
        row = self.rows["missed-comparison"]
        assessment(row["response"], "duplicates")["conclusion"] = "no_issue_found"
        self.assert_bad(
            "incomplete_duplicate_clean", row["request"], row["response"], plan(row)
        )

    def test_missing_required_comparison_forbids_completed(self):
        row = self.rows["missed-comparison"]
        row["response"]["coverage"][0]["disposition"] = "completed"
        self.assert_bad(
            "comparison_incomplete_coverage", row["request"], row["response"]
        )

    def test_plan_mismatch_and_malformed_units(self):
        row = self.rows["partial-found"]
        self.assert_bad(
            "partial_plan_mismatch",
            row["request"],
            row["response"],
            ReviewPlan(ASSESSMENTS, frozenset()),
        )
        self.assert_bad(
            "partial_plan_invalid",
            row["request"],
            row["response"],
            ReviewPlan(frozenset({"made-up"}), frozenset({"other1"})),
        )
        self.assert_bad(
            "partial_plan_invalid",
            row["request"],
            row["response"],
            ReviewPlan(set(ASSESSMENTS), frozenset({"other1"})),
        )

    def test_known_skipped_assessment_is_explicit(self):
        self.resp["coverage"][0].update(
            disposition="partially_processed", reason="Две оценки не выполнялись."
        )
        for kind in ("contradictions", "ambiguity"):
            assessment(self.resp, kind).update(
                conclusion="inconclusive", considered_keys=[]
            )
        fixed = ReviewPlan(frozenset({"support"}), frozenset())
        validate_response(self.req, self.resp, review_plan=fixed)
        assessment(self.resp, "ambiguity")["conclusion"] = "no_issue_found"
        self.assert_bad("skipped_check_result", review_plan=fixed)

    def test_no_spurious_partial_for_fully_executed_plan(self):
        self.resp["coverage"][0].update(
            disposition="partially_processed", reason="Недоказанная частичность."
        )
        self.assert_bad(
            "partial_plan_not_partial", review_plan=ReviewPlan(ASSESSMENTS, frozenset())
        )

    def test_comparison_scope_required_and_roles(self):
        row = self.rows["other-requirement-duplicate"]
        row["request"]["input"]["comparison_scope"]["required_keys"] = []
        self.assert_bad("comparison_required_set", row["request"], row["response"])
        row["request"]["input"]["comparison_scope"]["required_keys"] = ["ghost"]
        self.assert_bad(
            "comparison_required_reference", row["request"], row["response"]
        )

    def test_selected_scope_requires_reason(self):
        row = self.rows["selected"]
        row["request"]["input"]["comparison_scope"].pop("selection_reason")
        self.assert_bad("schema", row["request"], row["response"])

    def test_target_and_repeated_comparison_are_excluded(self):
        row = self.rows["other-requirement-duplicate"]
        row["request"]["input"]["comparisons"][0]["ref"] = deepcopy(
            row["request"]["input"]["target"]["ref"]
        )
        self.assert_bad(
            "comparison_repeated_or_target", row["request"], row["response"]
        )
        row = self.rows["partial-found"]
        row["request"]["input"]["comparisons"][1]["ref"] = deepcopy(
            row["request"]["input"]["comparisons"][0]["ref"]
        )
        self.assert_bad(
            "comparison_repeated_or_target", row["request"], row["response"], plan(row)
        )

    def test_pending_change_proposal_and_all_roles(self):
        row = self.rows["other-requirement-duplicate"]
        comparison = row["request"]["input"]["comparisons"][0]
        comparison["roles"] = ["current", "pending_change", "new_candidate", "history"]
        validate_request(row["request"])
        comparison.pop("proposal_ref")
        self.assert_bad("schema", row["request"], row["response"])

    def test_same_requirement_never_becomes_other_duplicate(self):
        row = self.rows["other-requirement-duplicate"]
        row["request"]["input"]["comparisons"][0]["requirement_id"] = row["request"][
            "input"
        ]["target"]["requirement_id"]
        self.assert_bad("duplicate_same_requirement", row["request"], row["response"])

    def test_considered_roles(self):
        row = self.rows["other-requirement-duplicate"]
        assessment(row["response"], "support")["considered_keys"].append("other1")
        self.assert_bad("check_considered_role", row["request"], row["response"])
        assessment(self.resp, "duplicates")["considered_keys"] = ["f1"]
        self.assert_bad("comparison_considered_role")

    def test_issue_and_assessment_consistency(self):
        row = self.rows["unsupported"]
        assessment(row["response"], "support")["conclusion"] = "no_issue_found"
        self.assert_bad("issue_check_conflict", row["request"], row["response"])
        assessment(self.resp, "support")["conclusion"] = "issues_found"
        self.assert_bad("check_issue_missing")

    def test_issue_questions_and_scope(self):
        row = self.rows["insufficient-evidence"]
        row["response"]["result"]["issues"][0]["question_ids"] = ["ghost"]
        self.assert_bad("issue_question_reference", row["request"], row["response"])
        row["response"]["result"]["issues"][0]["question_ids"] = ["q1"]
        row["response"]["questions"][0]["related"] = [{"origin": "input", "key": "e1"}]
        self.assert_bad("question_scope", row["request"], row["response"])

    def test_global_ids_and_unknown_related(self):
        row = self.rows["insufficient-evidence"]
        row["response"]["uncertainties"][0]["local_id"] = "q1"
        self.assert_bad("local_id_unique", row["request"], row["response"])
        row["response"]["uncertainties"][0]["local_id"] = "u1"
        row["response"]["result"]["issues"][0]["related"] = [
            {"origin": "input", "key": "ghost"}
        ]
        self.assert_bad("related_reference", row["request"], row["response"])

    def test_severity_and_blocking_independent(self):
        row = self.rows["unsupported"]
        issue = row["response"]["result"]["issues"][0]
        for severity, blocking in (("high", False), ("low", True)):
            issue.update(
                severity=severity,
                blocking=blocking,
                blocking_reason="Блокировка обоснована отдельно от серьёзности.",
            )
            validate_response(row["request"], row["response"])

    def test_unresolved_fresh_question_cannot_be_only_clean(self):
        row = self.rows["uncertain-speech"]
        # Isolate the unresolved-question rule from insufficient-coverage checks.
        row["response"]["coverage"][0]["disposition"] = "completed"
        assessment(row["response"], "support")["conclusion"] = "no_issue_found"
        self.assert_bad("unresolved_clean_result", row["request"], row["response"])

    def test_prior_blocker_stays_open_despite_new_clean(self):
        row = self.rows["previous-open-blocker"]
        before = deepcopy(row["request"])
        result = verify_requirement(
            row["request"],
            Replay(json.dumps(row["response"])),
            verify_context=lambda _: None,
        )
        self.assertEqual(row["request"], before)
        self.assertEqual(result["result"]["issues"], [])
        self.assertTrue(
            any(
                i["is_open"] and i["blocking"]
                for c in before["input"]["previous_checks"]
                for i in c["issues"]
            )
        )

    def test_followup_requires_exact_result_and_issue(self):
        row = self.rows["followup"]
        row["request"]["input"]["followup"]["previous_result_ref"]["state_id"] = "stale"
        self.assert_bad("followup_result", row["request"], row["response"])
        row["request"]["input"]["followup"]["previous_result_ref"] = deepcopy(
            row["request"]["input"]["previous_checks"][0]["ref"]
        )
        row["request"]["input"]["followup"]["issue_refs"][0]["state_id"] = "stale"
        self.assert_bad("followup_issue", row["request"], row["response"])

    def test_required_context_rejected_before_model(self):
        provider = Mock()
        with self.assertRaises(VerificationError) as caught:
            verify_requirement(
                self.req,
                provider,
                verify_context=lambda _: None,
                required_context=frozenset({"prior_decision"}),
            )
        self.assertEqual(caught.exception.rule, "required_context_missing")
        provider.verify.assert_not_called()
        validate_request(
            self.rows["approved-change"]["request"],
            required_context=frozenset({"prior_decision", "change_context"}),
        )

    def test_change_base_belongs_to_same_requirement(self):
        row = self.rows["approved-change"]
        row["request"]["input"]["comparisons"][0]["requirement_id"] = "FOREIGN-REQ"
        self.assert_bad("change_base_requirement", row["request"], row["response"])

    def test_input_evidence_closure(self):
        self.req["input"]["target"]["evidence"][0]["finding_key"] = "ghost"
        self.assert_bad("target_finding_reference")
        self.req["input"]["target"]["evidence"][0]["finding_key"] = "f1"
        self.req["input"]["target"]["evidence"][0]["links"][0]["fragment_key"] = "ghost"
        self.assert_bad("target_evidence_mismatch")

    def test_deleted_sources_not_restored_and_speech_not_promoted(self):
        for name in ("all-deleted", "uncertain-speech"):
            row = self.rows[name]
            before = deepcopy(row["request"])
            validate_response(row["request"], row["response"])
            self.assertEqual(row["request"], before)
        self.assertFalse(self.rows["all-deleted"]["request"]["input"]["fragments"])

    def test_all_deleted_evidence_cannot_be_clean_support(self):
        row = self.rows["all-deleted"]
        assessment(row["response"], "support")["conclusion"] = "no_issue_found"
        self.assert_bad(
            "support_without_available_evidence", row["request"], row["response"]
        )

    def test_semantic_counterexamples_only_pass_technical_checks(self):
        for row in semantic_counterexamples():
            self.assertEqual(row["fixture_role"], "intentional_semantic_error")
            validate_response(row["request"], row["response"])

    def test_strict_parser_safe_errors(self):
        for raw in (
            '{"secret":1,"secret":2}',
            '{"a":NaN}',
            '{"a":1e999}',
            "{",
            b"\xff",
        ):
            with (
                self.subTest(raw_type=type(raw)),
                self.assertRaises(VerificationError) as caught,
            ):
                decode(raw)
            self.assertNotIn("secret", str(caught.exception))

    def test_verifier_prevents_foreign_project_state_history_calls(self):
        provider = Mock()
        for reason in (
            "cross_project",
            "wrong_state",
            "wrong_scope",
            "wrong_decision",
            "revoked_access",
            "quote_mismatch",
        ):
            with (
                self.subTest(reason=reason),
                self.assertRaises(VerificationError) as caught,
            ):
                verify_requirement(
                    self.req,
                    provider,
                    verify_context=Mock(side_effect=ValueError("private " + reason)),
                )
            self.assertEqual(
                str(caught.exception), "invalid_request:context_not_verified"
            )
        provider.verify.assert_not_called()

    def test_snapshot_isolated_from_callbacks(self):
        before = deepcopy(self.req)
        provider = Mock()

        def verify(value):
            value["input"]["target"]["text"] = "mutated"

        def execute(value):
            self.assertEqual(value, before)
            value["input"].clear()
            return json.dumps(self.resp)

        provider.verify.side_effect = execute
        self.assertEqual(
            verify_requirement(self.req, provider, verify_context=verify), self.resp
        )
        self.assertEqual(self.req, before)

    def test_timeout_and_provider_errors_no_fake_results(self):
        for error, code in (
            (TimeoutError("private"), "timeout"),
            (RuntimeError("private"), "provider_error"),
            (VerificationError("private", "private"), "provider_error"),
        ):
            provider = Mock()
            provider.verify.side_effect = error
            with (
                self.subTest(code=code),
                self.assertRaises(VerificationError) as caught,
            ):
                verify_requirement(self.req, provider, verify_context=lambda _: None)
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private", str(caught.exception))

    def test_real_transfer_disabled(self):
        with (
            patch("ai.group_findings.provider.build_opener") as opener,
            self.assertRaises(VerificationError),
        ):
            Ollama(
                OllamaConfig("http://localhost:11434/api/chat", "NOT_SELECTED")
            ).verify(self.req)
        opener.assert_not_called()

    def test_transport_schema_and_system_data_separation(self):
        row = self.rows["injection"]
        transport = MagicMock()
        transport.open.return_value.__enter__.return_value.read.return_value = (
            json.dumps(
                {"done": True, "message": {"content": json.dumps(row["response"])}}
            ).encode()
        )
        with patch("ai.group_findings.provider.build_opener", return_value=transport):
            verify_requirement(
                row["request"],
                Ollama(
                    OllamaConfig(
                        "http://localhost:11434/api/chat", "synthetic-transport", True
                    )
                ),
                verify_context=lambda _: None,
            )
        payload = json.loads(transport.open.call_args.args[0].data)
        self.assertEqual(payload["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(json.loads(payload["messages"][1]["content"]), row["request"])
        self.assertIn("checks", payload["format"]["properties"]["result"]["properties"])
        self.assertNotIn("закрой старые блокеры", payload["messages"][0]["content"])

    def test_envelope_and_transport_timeout(self):
        transport = MagicMock()
        transport.open.return_value.__enter__.return_value.read.return_value = (
            b'{"done":false}'
        )
        with (
            patch("ai.group_findings.provider.build_opener", return_value=transport),
            self.assertRaises(VerificationError) as caught,
        ):
            Ollama(OllamaConfig("http://host/api/chat", "m", True)).verify(self.req)
        self.assertEqual(caught.exception.rule, "provider_envelope")
        transport.open.side_effect = URLError(TimeoutError())
        with (
            patch("ai.group_findings.provider.build_opener", return_value=transport),
            self.assertRaises(VerificationError) as caught,
        ):
            Ollama(OllamaConfig("http://host/api/chat", "m", True)).verify(self.req)
        self.assertEqual(caught.exception.code, "timeout")

    def test_cli_synthetic_no_overwrite_and_partial_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            command = [
                sys.executable,
                "-B",
                "-m",
                "ai.verify_requirement",
                "--request",
                str(ROOT / "evals/ai/verification/partial.request.json"),
                "--synthetic-response",
                str(ROOT / "evals/ai/verification/partial.response.json"),
                "--output",
                str(folder / "out.json"),
                "--synthetic-plan",
                str(ROOT / "evals/ai/verification/partial.plan.json"),
            ]
            first = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, check=False
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("model=none; semantic_quality=not_evaluated", first.stdout)
            saved = (folder / "out.json").read_bytes()
            second = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, check=False
            )
            self.assertEqual(second.returncode, 2)
            self.assertEqual((folder / "out.json").read_bytes(), saved)
            missing = subprocess.run(
                command[:-2], cwd=ROOT, capture_output=True, text=True, check=False
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn("partial_plan_required", missing.stderr)


if __name__ == "__main__":
    unittest.main()
