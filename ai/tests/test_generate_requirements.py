"""Structural/link acceptance and synthetic semantic review controls; no inference."""

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

from ai.generate_requirements import (
    GenerationError,
    generate_requirements,
    validate_request,
    validate_response,
)
from ai.generate_requirements.prompt import SYSTEM_PROMPT
from ai.generate_requirements.provider import Ollama, OllamaConfig, Replay
from ai.generate_requirements.validation import decode, response_format
from ai.group_findings.validation import MAX_JSON_BYTES
from evals.ai.generation.build_cases import (
    artifacts,
    candidate,
    cases,
    request,
    response,
)

ROOT = Path(__file__).resolve().parents[2]


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case["id"]: case for case in cases()}
        self.req = deepcopy(self.cases["independent"]["request"])
        self.resp = deepcopy(self.cases["independent"]["response"])

    def assert_bad(self, rule, req=None, resp=None):
        with self.assertRaises(GenerationError) as caught:
            validate_response(
                self.req if req is None else req, self.resp if resp is None else resp
            )
        self.assertEqual(caught.exception.rule, rule)

    def test_all_synthetic_controls_and_mappings(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                self.assertEqual(
                    validate_response(case["request"], case["response"]),
                    case["response"],
                )

    def test_reproducible_artifacts(self):
        for name, value in artifacts().items():
            self.assertEqual(
                (ROOT / "evals/ai/generation" / name).read_text("utf-8"),
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            )

    def test_approved_examples(self):
        examples = ROOT / "docs/contracts/ai/examples"
        req = json.loads(
            (examples / "generate_requirements.valid.request.json").read_text("utf-8")
        )
        for name in (
            "generate_requirements.valid",
            "generate.no-requirements",
            "generate.blocking-question",
            "generate.nonblocking-question",
        ):
            resp = json.loads((examples / (name + ".response.json")).read_text("utf-8"))
            validate_response(req, resp)
        validate_request(
            json.loads(
                (examples / "generate.previous-context.request.json").read_text("utf-8")
            )
        )

    def test_self_contained_schema_is_not_group_schema(self):
        schema = response_format()
        Draft202012Validator(schema).validate(self.resp)
        self.assertIn("RequirementCandidate", schema["$defs"])
        self.assertNotIn("GroupCandidate", schema["$defs"])
        self.assertNotIn(
            "https://feedback2req.invalid/contracts/ai/v1/common.schema.json#",
            json.dumps(schema),
        )

    def test_many_to_many_evidence(self):
        for name, count, selection_count in (
            ("several-findings", 1, 2),
            ("several-from-one", 2, 1),
        ):
            row = self.cases[name]
            accepted = validate_response(row["request"], row["response"])
            self.assertEqual(len(accepted["result"]["requirements"]), count)
            self.assertEqual(
                len(accepted["result"]["requirements"][0]["evidence"]), selection_count
            )

    def test_source_chain_preserves_conditions_and_modes_in_fixture(self):
        row = self.cases["bounded-export"]
        accepted = generate_requirements(
            row["request"],
            Replay(json.dumps(row["response"])),
            verify_context=lambda _: None,
        )
        self.assertIn(
            "При наличии отмеченных записей",
            accepted["result"]["requirements"][0]["text"],
        )
        self.assertFalse(accepted["questions"][0]["blocking"])
        self.assertNotIn("CSV", accepted["result"]["requirements"][0]["text"])
        inferred = self.cases["need-vs-solution"]
        self.assertEqual(
            inferred["request"]["input"]["findings"][0]["mode"], "inferred"
        )
        self.assertIn(
            "интерпретация AI",
            inferred["response"]["result"]["requirements"][0]["rationale"],
        )

    def test_conflict_keeps_independent_candidate(self):
        row = self.cases["conflict-with-independent"]
        result = validate_response(row["request"], row["response"])
        self.assertEqual(
            result["result"]["requirements"][0]["evidence"][0]["finding_key"], "f3"
        )
        self.assertEqual(
            [c["disposition"] for c in result["coverage"][:2]],
            ["insufficient_information"] * 2,
        )
        self.assertEqual(
            {r["key"] for r in result["questions"][0]["related"]}, {"f1", "f2"}
        )

    def test_semantic_counterexamples_are_explicit_and_not_automatically_detected(self):
        values = artifacts()["cases.json"]
        self.assertFalse(values["semantic_gold"])
        for row in values["semantic_counterexamples"]:
            self.assertEqual(row["fixture_role"], "intentional_semantic_error")
            # Connectivity alone cannot detect a lost condition or invented design.
            validate_response(row["request"], row["response"])

    def test_empty_completed_needs_reason_even_with_other_candidates(self):
        self.resp["result"]["requirements"].pop()
        self.assert_bad("empty_result_reason")
        self.resp["coverage"][1]["reason"] = "Независимый кандидат не обоснован."
        validate_response(self.req, self.resp)

    def test_successful_empty_is_not_technical_failure(self):
        row = self.cases["successful-empty"]
        self.assertEqual(
            validate_response(row["request"], row["response"])["result"][
                "requirements"
            ],
            [],
        )
        row["response"]["coverage"][0].pop("reason")
        self.assert_bad("schema", row["request"], row["response"])

    def test_mixed_coverage_is_preserved(self):
        row = self.cases["mixed-coverage"]
        result = validate_response(row["request"], row["response"])
        self.assertEqual(
            [c["disposition"] for c in result["coverage"]],
            ["completed", "not_processed", "insufficient_information"],
        )
        self.assertEqual(len(result["result"]["requirements"]), 1)

    def test_not_processed_cannot_support_or_be_considered(self):
        self.resp["coverage"][0].update(
            reviewed=False, disposition="not_processed", reason="Пропуск."
        )
        self.assert_bad("unreviewed_result")

    def test_unverifiable_internal_partial_is_rejected(self):
        self.resp["coverage"][0].update(
            disposition="partially_processed", reason="Часть смысла пропущена."
        )
        self.assert_bad("partial_scope_unverifiable")

    def test_coverage_must_match_all_primary_keys_once(self):
        for key in ("f1", "e2", "foreign"):
            resp = deepcopy(self.resp)
            resp["coverage"][1]["input_key"] = key
            self.assert_bad("coverage_keys", resp=resp)
        self.resp["coverage"].pop()
        self.assert_bad("coverage_keys")

    def test_roles_of_considered_context_and_evidence(self):
        for field, value, rule in (
            ("considered_keys", ["e1"], "considered_role"),
            ("context_keys", ["e1"], "context_role"),
            ("context_keys", ["f1"], "context_role"),
            (
                "evidence",
                [{"finding_key": "ghost", "fragment_keys": ["e1"]}],
                "evidence_finding",
            ),
            (
                "evidence",
                [{"finding_key": "f2", "fragment_keys": ["e2"]}],
                "evidence_not_considered",
            ),
            (
                "evidence",
                [{"finding_key": "f1", "fragment_keys": ["e2"]}],
                "evidence_fragment",
            ),
            (
                "evidence",
                [{"finding_key": "f1", "fragment_keys": ["ghost"]}],
                "evidence_fragment",
            ),
        ):
            with self.subTest(field=field, rule=rule):
                resp = deepcopy(self.resp)
                resp["result"]["requirements"][0][field] = value
                self.assert_bad(rule, resp=resp)

    def test_input_keys_and_missing_links(self):
        self.req["input"]["fragments"][0]["key"] = "f1"
        self.assert_bad("key_unique")
        self.req["input"]["fragments"][0]["key"] = "missing"
        self.assert_bad("evidence_reference")

    def test_fragment_source_and_locator_are_checked(self):
        self.req["input"]["fragments"][0]["locator"]["end"] += 1
        self.assert_bad("locator_length")
        req = request(["😀Сохранять фильтры."])
        validate_response(req, response(req, [candidate("Сохранять фильтры.")]))
        req["input"]["fragments"][0]["text_ref"]["state_id"] = "foreign"
        self.assert_bad(
            "text_source", req, response(req, [candidate("Сохранять фильтры.")])
        )

    def test_previous_candidates_must_have_closed_evidence(self):
        row = self.cases["regeneration"]
        old = row["request"]["input"]["previous_candidates"][0]
        old["evidence"][0]["finding_key"] = "ghost"
        self.assert_bad("previous_finding_reference", row["request"], row["response"])
        old["evidence"][0]["finding_key"] = "f1"
        old["evidence"][0]["links"][0]["fragment_key"] = "ghost"
        self.assert_bad("previous_evidence_mismatch", row["request"], row["response"])

    def test_previous_revision_is_not_new_evidence_or_context(self):
        row = self.cases["regeneration"]
        row["response"]["result"]["requirements"][0]["context_keys"] = ["p1"]
        self.assert_bad("context_role", row["request"], row["response"])

    def test_question_scope_and_related_resolution(self):
        row = self.cases["insufficient"]
        for origin, key, rule in (
            ("input", "e1", "question_scope"),
            ("input", "ghost", "related_reference"),
            ("output", "q1", "question_scope"),
        ):
            result = deepcopy(row["response"])
            result["questions"][0]["related"] = [{"origin": origin, "key": key}]
            self.assert_bad(rule, row["request"], result)

    def test_questions_may_target_candidate_or_previous_revision(self):
        row = self.cases["regeneration"]
        q = deepcopy(self.cases["insufficient"]["response"]["questions"][0])
        q["related"] = [
            {"origin": "input", "key": "p1"},
            {"origin": "output", "key": "r1"},
        ]
        row["response"]["questions"] = [q]
        validate_response(row["request"], row["response"])

    def test_global_output_ids_and_closed_fields(self):
        self.resp["result"]["requirements"][1]["local_id"] = "r1"
        self.assert_bad("local_id_unique")
        self.resp["result"]["requirements"][1]["local_id"] = "r2"
        for field in (
            "approved",
            "acceptance_criteria",
            "C(r)",
            "id",
            "revision_number",
        ):
            result = deepcopy(self.resp)
            result["result"]["requirements"][0][field] = True
            self.assert_bad("schema", resp=result)

    def test_deleted_evidence_cannot_be_selected_as_available(self):
        self.req["input"]["findings"][0]["evidence"] = [
            {"kind": "deleted_source", "source_id": "s1"}
        ]
        self.assert_bad("deleted_source")
        self.req["input"]["fragments"].pop(0)
        self.assert_bad("evidence_fragment")
        self.resp["result"]["requirements"].pop(0)
        self.resp["coverage"][0].update(
            disposition="insufficient_information",
            reason="Доступное основание утрачено.",
        )
        validate_response(self.req, self.resp)

    def test_strict_json_reused_without_repairs(self):
        for raw in (
            '{"a":1,"a":2}',
            '{"a":NaN}',
            '{"a":1e999}',
            "{",
            b"\xff",
            " " * (MAX_JSON_BYTES + 1),
        ):
            with self.subTest(raw_type=type(raw)), self.assertRaises(GenerationError):
                decode(raw)

    def test_verifier_prevents_model_call_on_untrusted_context(self):
        provider = Mock()
        for reason in (
            "cross_project",
            "stale_state",
            "revoked_access",
            "wrong_quote",
            "unavailable",
        ):
            with (
                self.subTest(reason=reason),
                self.assertRaises(GenerationError) as caught,
            ):
                generate_requirements(
                    self.req,
                    provider,
                    verify_context=Mock(side_effect=ValueError("private " + reason)),
                )
            self.assertEqual(
                str(caught.exception), "invalid_request:context_not_verified"
            )
        provider.generate.assert_not_called()

    def test_mutating_verifier_and_adapter_cannot_change_snapshot(self):
        before = deepcopy(self.req)
        provider = Mock()

        def verify(value):
            value["input"]["findings"].clear()

        def execute(value):
            self.assertEqual(value, before)
            value["input"]["findings"].clear()
            return json.dumps(self.resp)

        provider.generate.side_effect = execute
        self.assertEqual(
            generate_requirements(self.req, provider, verify_context=verify), self.resp
        )
        self.assertEqual(self.req, before)

    def test_timeout_and_provider_failure_are_safe_and_have_no_fake_coverage(self):
        for error, code in (
            (TimeoutError("private"), "timeout"),
            (RuntimeError("private"), "provider_error"),
            (GenerationError("private", "private"), "provider_error"),
        ):
            with self.subTest(code=code), self.assertRaises(GenerationError) as caught:
                provider = Mock()
                provider.generate.side_effect = error
                generate_requirements(self.req, provider, verify_context=lambda _: None)
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private", str(caught.exception))

    def test_gate_disables_real_model_by_default(self):
        with (
            patch("ai.group_findings.provider.build_opener") as opener,
            self.assertRaises(GenerationError),
        ):
            Ollama(
                OllamaConfig("http://localhost:11434/api/chat", "not-selected")
            ).generate(self.req)
        opener.assert_not_called()

    def test_transport_uses_generation_schema_and_separates_untrusted_content(self):
        row = self.cases["injection"]
        transport = MagicMock()
        transport.open.return_value.__enter__.return_value.read.return_value = (
            json.dumps(
                {"done": True, "message": {"content": json.dumps(row["response"])}}
            ).encode()
        )
        with patch("ai.group_findings.provider.build_opener", return_value=transport):
            generate_requirements(
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
        self.assertIn(
            "requirements", payload["format"]["properties"]["result"]["properties"]
        )
        self.assertNotIn("evil.invalid", payload["messages"][0]["content"])

    def test_incomplete_transport_envelope_is_rejected(self):
        transport = MagicMock()
        transport.open.return_value.__enter__.return_value.read.return_value = (
            b'{"done":false}'
        )
        with (
            patch("ai.group_findings.provider.build_opener", return_value=transport),
            self.assertRaises(GenerationError) as caught,
        ):
            Ollama(OllamaConfig("http://localhost:11434/api/chat", "m", True)).generate(
                self.req
            )
        self.assertEqual(caught.exception.rule, "provider_envelope")

    def test_url_timeout_remains_timeout(self):
        transport = Mock()
        transport.open.side_effect = URLError(TimeoutError())
        with (
            patch("ai.group_findings.provider.build_opener", return_value=transport),
            self.assertRaises(GenerationError) as caught,
        ):
            Ollama(OllamaConfig("http://localhost:11434/api/chat", "m", True)).generate(
                self.req
            )
        self.assertEqual(caught.exception.code, "timeout")

    def test_cli_is_synthetic_private_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            req, resp, out = (
                folder / name for name in ("request.json", "response.json", "out.json")
            )
            req.write_text(json.dumps(self.req), "utf-8")
            resp.write_text(json.dumps(self.resp), "utf-8")
            command = [
                sys.executable,
                "-B",
                "-m",
                "ai.generate_requirements",
                "--request",
                str(req),
                "--synthetic-response",
                str(resp),
                "--output",
                str(out),
            ]
            first = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, check=False
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("model=none; semantic_quality=not_evaluated", first.stdout)
            saved = out.read_bytes()
            repeated = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, check=False
            )
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(out.read_bytes(), saved)
            resp.write_text('{"private":"confidential-material"}', "utf-8")
            failed = subprocess.run(
                command[:-1] + [str(folder / "bad.json")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertNotIn("confidential-material", failed.stdout + failed.stderr)
            self.assertFalse((folder / "bad.json").exists())


if __name__ == "__main__":
    unittest.main()
