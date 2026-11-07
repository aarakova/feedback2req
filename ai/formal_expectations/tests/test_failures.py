import json
import subprocess
import sys
import unittest
from copy import deepcopy
from unittest.mock import patch

import z3

from ai.formal_expectations import Limits, analyze
from ai.formal_expectations.tests.cases import interval, request, uncertain


class FailureTests(unittest.TestCase):
    def assert_failure(self, value, code, rule=None, **kwargs):
        result = analyze(value, **kwargs)
        self.assertIsNone(result.classification, result.to_dict())
        self.assertFalse(result.complete)
        self.assertEqual(result.diagnostic.code, code, result.to_dict())
        if rule is not None:
            self.assertEqual(result.diagnostic.rule, rule)
        return result

    def test_solver_unknown_timeout_and_resources_are_distinct(self):
        for reason, code in (
            ("incomplete theory", "solver_unknown"),
            ("timeout", "timeout"),
            ("max. resource limit exceeded", "resource_limit"),
            ("out of memory", "resource_limit"),
            ("canceled", "solver_unknown"),
        ):
            with (
                self.subTest(reason=reason),
                patch("ai.formal_expectations.solver.z3.Solver.check", return_value=z3.unknown),
                patch(
                    "ai.formal_expectations.solver.z3.Solver.reason_unknown", return_value=reason
                ),
            ):
                result = self.assert_failure(request(), code)
                self.assertEqual(result.checks[-1].state, code)

    def test_solver_exceptions_internal_failure_and_sanitization(self):
        for exception, code in (
            (z3.Z3Exception("SECRET"), "solver_failure"),
            (TimeoutError("SECRET"), "timeout"),
            (MemoryError("SECRET"), "resource_limit"),
            (RuntimeError("SECRET"), "internal_failure"),
        ):
            with (
                self.subTest(code=code),
                patch("ai.formal_expectations.solver.z3.Solver.check", side_effect=exception),
            ):
                result = self.assert_failure(request(), code)
                self.assertNotIn("SECRET", json.dumps(result.to_dict()))

    def test_failure_after_one_class_is_not_a_proof(self):
        with (
            patch(
                "ai.formal_expectations.solver.z3.Solver.check",
                side_effect=[z3.sat, z3.unsat, z3.unknown],
            ),
            patch("ai.formal_expectations.solver.z3.Solver.reason_unknown", return_value="timeout"),
        ):
            result = self.assert_failure(uncertain(), "timeout")
            self.assertEqual(result.variants_checked, 1)
            self.assertEqual(result.observed_classes, ("K",))

    def test_resource_limit_from_real_z3(self):
        self.assert_failure(request(), "resource_limit", limits=Limits(solver_rlimit=1))

    def test_variant_and_call_limits(self):
        self.assert_failure(
            uncertain(), "resource_limit", "variant_limit", limits=Limits(max_variants=1)
        )
        result = self.assert_failure(
            uncertain(), "resource_limit", "solver_calls", limits=Limits(max_solver_calls=3)
        )
        self.assertEqual(result.variants_checked, 1)
        self.assertEqual(result.checks[-1].state, "resource_limit")

    def test_total_deadline_without_flaky_sleep(self):
        with patch("ai.formal_expectations.limits.monotonic", side_effect=[0, 1]):
            self.assert_failure(
                request(), "timeout", "total_deadline", limits=Limits(total_timeout_ms=1)
            )

    def test_deadline_expiring_during_real_solver_result(self):
        # The actual native check returns sat, but its overdue result cannot be published.
        actual = z3.Solver.check
        clock = [0.0]

        def overdue(solver, *args):
            result = actual(solver, *args)
            clock[0] = 10.0
            return result

        with (
            patch("ai.formal_expectations.solver.z3.Solver.check", overdue),
            patch("ai.formal_expectations.limits.monotonic", side_effect=lambda: clock[0]),
        ):
            self.assert_failure(request(), "timeout")

    def test_deadline_expiring_during_translation_skips_native_check(self):
        from ai.formal_expectations.solver import Engine

        clock = [0.0]
        actual = Engine._constraint

        def overdue(engine, *args):
            result = actual(engine, *args)
            clock[0] = 10.0
            return result

        with (
            patch.object(Engine, "_constraint", overdue),
            patch("ai.formal_expectations.limits.monotonic", side_effect=lambda: clock[0]),
            patch("ai.formal_expectations.solver.z3.Solver.check", return_value=z3.sat) as check,
        ):
            self.assert_failure(request(), "timeout", "total_deadline")
            # The conditions query runs before value translation exhausts time.
            self.assertEqual(check.call_count, 1)

    def test_invalid_limit_configuration(self):
        for value in (0, -1, True, 1.5, "10", 2**32):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Limits(max_variants=value)

    def test_strict_closed_grammar(self):
        mutations = [
            (lambda v: v.update(formula="True"), "unsupported_input"),
            (lambda v: v.update(format_version="2"), "unsupported_input"),
            (lambda v: v.pop("left"), "invalid_input"),
            (lambda v: v["left"].pop("conditions"), "invalid_input"),
            (lambda v: v["left"].update(basis=""), "invalid_input"),
            (lambda v: v["left"].update(conditions=[]), "invalid_formalization"),
            (lambda v: v["left"].update(conditions=["online", "online"]), "invalid_input"),
            (lambda v: v["left"].update(conditions=["unknown"]), "invalid_formalization"),
            (lambda v: v["left"]["values"].update(lower=True), "invalid_input"),
            (lambda v: v["left"]["values"].update(lower=1.2), "invalid_input"),
            (lambda v: v["left"]["values"].update(lower="NaN"), "invalid_input"),
            (lambda v: v["left"]["values"].update(lower="1e2"), "invalid_input"),
            (lambda v: v["left"]["values"].update(unit="hour"), "unsupported_input"),
            (lambda v: v["model"]["domain"].update(dimension="length"), "invalid_formalization"),
            (lambda v: v["left"]["values"].update(kind="expression"), "unsupported_input"),
            (lambda v: v["left"]["values"].update(depends_on="situation"), "unsupported_input"),
            (lambda v: v["model"].update(situations=[]), "invalid_formalization"),
            (
                lambda v: v["left"].update(values={"kind": "enum", "allowed": ["a"]}),
                "invalid_formalization",
            ),
        ]
        for mutation, code in mutations:
            with self.subTest(mutation=mutation):
                value = request()
                mutation(value)
                self.assert_failure(value, code)

    def test_empty_and_duplicate_enum_and_boolean_constraints(self):
        for kind, members in (("boolean", [False, True]), ("enum", ["a", "b"])):
            for bad, expected in (
                ([], "invalid_formalization"),
                (members + members, "invalid_input"),
            ):
                with self.subTest(kind=kind, bad=bad):
                    value = request()
                    value["model"]["domain"] = {"kind": kind, "allowed": members}
                    value["left"]["values"] = {"kind": kind, "allowed": bad}
                    self.assert_failure(value, expected)

    def test_json_corruption_duplicates_nonfinite_and_types(self):
        for raw in (b"\xff", "{", '{"x":1,"x":2}', "NaN", "Infinity", "[]", "null", "1", '"text"'):
            with self.subTest(raw=raw):
                self.assert_failure(raw, "invalid_input")
        for value in (object(), {1: "value"}, {"x": object()}, {"x": float("inf")}, {"x": (1, 2)}):
            self.assert_failure(value, "invalid_input")

    def test_size_depth_and_cycle_limits(self):
        self.assert_failure(
            request(), "resource_limit", "input_bytes", limits=Limits(max_input_bytes=10)
        )
        self.assert_failure(
            json.dumps(request()),
            "resource_limit",
            "input_bytes",
            limits=Limits(max_input_bytes=10),
        )
        nested = []
        nested.append(nested)
        self.assert_failure(nested, "resource_limit", "json_complexity")
        self.assert_failure({"x": [0] * 50_001}, "resource_limit", "json_complexity")

    def test_payload_in_data_is_inert_and_payload_in_numeric_slot_is_rejected(self):
        payload = "__import__('pathlib').Path('SHOULD_NOT_EXIST').write_text('executed')"
        value = request()
        value["model"]["domain"] = {"kind": "enum", "allowed": [payload]}
        value["left"]["values"] = value["right"]["values"] = {"kind": "enum", "allowed": [payload]}
        value["left"]["basis"] = payload
        self.assertEqual(analyze(value).classification, "S")
        from pathlib import Path

        self.assertFalse(Path("SHOULD_NOT_EXIST").exists())
        value = request()
        value["left"]["values"]["lower"] = payload
        self.assert_failure(value, "invalid_input", "exact_decimal_required")

    def test_rejects_invalid_variant_even_after_two_different_classes(self):
        value = uncertain()
        bad = deepcopy(value["omega"]["variants"][0])
        bad["left"]["values"] = interval(9, 1)
        value["omega"]["variants"].append(bad)
        result = self.assert_failure(value, "invalid_formalization", "reversed_interval")
        self.assertEqual(result.variants_checked, 0)

    def test_cli_missing_file_invalid_json_and_limits(self):
        for args in (("absent-input.json",), ("-", "--max-variants", "0")):
            result = subprocess.run(
                [sys.executable, "-m", "ai.formal_expectations", *args],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
        result = subprocess.run(
            [sys.executable, "-m", "ai.formal_expectations", "-", "--max-input-bytes", "10"],
            input=json.dumps(request()),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["diagnostic"]["code"], "resource_limit")


if __name__ == "__main__":
    unittest.main()
