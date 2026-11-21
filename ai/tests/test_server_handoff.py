"""Exercise service boundaries with independent synthetic trusted-state checks.

The evaluator verifies fixture facts here, not real permissions or database state.
No server storage, queue, or new public contract is implemented by these tests.
"""

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals/ai"))

from checks import check_request
from runner import Dataset

from ai.generate_requirements import GenerationError, generate_requirements
from ai.verify_requirement import VerificationError, verify_requirement

SERVICES = (
    ("generate", generate_requirements, GenerationError, "generate"),
    ("verify", verify_requirement, VerificationError, "verify"),
)


class ServerHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = Dataset()

    def example(self, name):
        case = "S06" if name == "verify" else "S01"
        return deepcopy(self.dataset.examples[(case, name)])

    def verifier(self, trusted, events):
        def verify(request):
            events.append("trusted_check")
            if check_request(self.dataset.contracts, request, trusted):
                raise ValueError("PRIVATE-TRUSTED-FACT")

        return verify

    def test_saved_snapshot_is_checked_before_one_provider_call(self):
        for name, service, _, method in SERVICES:
            with self.subTest(operation=name):
                example = self.example(name)
                before, events = deepcopy(example), []
                provider = Mock()

                def execute(request, events=events, before=before, example=example):
                    events.append("provider")
                    self.assertEqual(request, before["request"])
                    return json.dumps(example["fixture_response"])

                getattr(provider, method).side_effect = execute
                result = service(
                    example["request"],
                    provider,
                    verify_context=self.verifier(example["trusted"], events),
                )
                self.assertEqual(result, before["fixture_response"])
                self.assertEqual(example, before)
                self.assertEqual(events, ["trusted_check", "provider"])
                getattr(provider, method).assert_called_once()

    def test_untrusted_facts_block_both_services_before_provider(self):
        for name, service, error_class, method in SERVICES:
            for fault in ("quote", "locator", "reliability", "project", "state"):
                with self.subTest(operation=name, fault=fault):
                    example = self.example(name)
                    fragment = example["request"]["input"]["fragments"][0]
                    if fault == "quote":
                        # Preserve length so only the trusted text can expose this.
                        fragment["quote"] = "!" + fragment["quote"][1:]
                    elif fault == "locator":
                        fragment["locator"] = {
                            k: v + 1 for k, v in fragment["locator"].items()
                        }
                    elif fault == "reliability":
                        fragment["reliability"] = "uncertain"
                    elif fault == "project":
                        example["request"]["project_id"] = "another-project"
                    else:
                        example["trusted"]["states"] = []
                    events, provider = [], Mock()
                    with self.assertRaises(error_class) as caught:
                        service(
                            example["request"],
                            provider,
                            verify_context=self.verifier(example["trusted"], events),
                        )
                    self.assertEqual(
                        str(caught.exception), "invalid_request:context_not_verified"
                    )
                    self.assertEqual(events, ["trusted_check"])
                    getattr(provider, method).assert_not_called()

    def test_verification_checks_trusted_comparison_and_history_snapshots(self):
        for field in ("comparison_scope", "previous_checks"):
            with self.subTest(field=field):
                example = self.example("verify")
                # Omission in the request cannot establish absence in application state.
                example["trusted"][field] = None
                provider = Mock()
                with self.assertRaises(VerificationError) as caught:
                    verify_requirement(
                        example["request"],
                        provider,
                        verify_context=self.verifier(example["trusted"], []),
                    )
                self.assertEqual(caught.exception.rule, "context_not_verified")
                provider.verify.assert_not_called()

    def test_invalid_response_is_rejected_without_automatic_retry(self):
        for name, service, error_class, method in SERVICES:
            with self.subTest(operation=name):
                example = self.example(name)
                events, provider = [], Mock()
                getattr(provider, method).side_effect = [
                    "{",
                    json.dumps(example["fixture_response"]),
                ]
                with self.assertRaises(error_class) as caught:
                    service(
                        example["request"],
                        provider,
                        verify_context=self.verifier(example["trusted"], events),
                    )
                self.assertEqual(caught.exception.code, "invalid_response")
                self.assertEqual(events, ["trusted_check"])
                getattr(provider, method).assert_called_once()


if __name__ == "__main__":
    unittest.main()
